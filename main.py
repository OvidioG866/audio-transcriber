import sys
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

# Set event loop policy for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
from datetime import datetime
from dotenv import load_dotenv
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from scraper import FTScraper
from prioritizator import GeopoliticalPrioritizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="FT Article Scraper")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your iOS app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
scraper = None
prioritizer = GeopoliticalPrioritizer()
scheduler = AsyncIOScheduler()

# Global variables for tracking scraping status
last_successful_scrape = None
last_scrape_error = None
all_articles = []

async def scheduled_scraping():
    """Run the scraping process at scheduled times."""
    global last_successful_scrape, last_scrape_error, all_articles
    logger.info("Starting scheduled scraping")
    try:
        if not scraper:
            logger.info("Initializing scraper for scheduled task")
            global scraper
            scraper = FTScraper()
            await scraper.initialize()
        
        # Get articles
        new_articles = await get_articles()
        
        # Update global variables
        current_time = datetime.now().isoformat()
        for article in new_articles:
            article['scraped_at'] = current_time
            all_articles.append(article)
        
        last_successful_scrape = current_time
        last_scrape_error = None
        logger.info(f"Scheduled scraping completed. Found {len(new_articles)} new articles")
        
    except Exception as e:
        last_scrape_error = str(e)
        logger.error(f"Error in scheduled scraping: {str(e)}")
    finally:
        # Don't cleanup the scraper, keep it running for next scheduled task
        pass

# Models
class ScraperConfig(BaseModel):
    username: Optional[str] = None
    uni_id: Optional[str] = None
    password: Optional[str] = None

class Article(BaseModel):
    headline: str
    url: str
    standfirst: Optional[str] = None
    full_text: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    priority_score: Optional[float] = None
    tags: Optional[List[str]] = None

class PrioritizedArticle(Article):
    summary: Optional[str] = None
    audio_url: Optional[str] = None
    processing_status: str = "pending"  # pending, processing, completed, failed

class ScrapingStatus(BaseModel):
    last_successful_scrape: Optional[str] = None
    total_articles: int = 0
    new_articles_since_last_scrape: int = 0
    next_scheduled_scrape: Optional[str] = None
    last_scrape_error: Optional[str] = None

class ArticleList(BaseModel):
    articles: List[Article]
    total_count: int
    last_updated: str

class ArticleRequest(BaseModel):
    url: str

class ArticleResponse(BaseModel):
    url: str
    title: str
    description: Optional[str] = None
    timestamp: Optional[str] = None
    author: Optional[str] = None
    topics: List[str] = []
    error: Optional[str] = None

# Routes
@app.post("/initialize")
async def initialize_scraper(credentials: ScraperConfig):
    """Initialize the scraper."""
    global scraper
    try:
        scraper = FTScraper(
            username=None,  # No login needed
            uni_id=None,    # No login needed
            password=None   # No login needed
        )
        
        # Initialize Selenium
        success = await scraper.initialize()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to initialize scraper")
            
        return {"status": "success", "message": "Scraper initialized successfully"}
            
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Selenium initialization failed: {str(e)}")

@app.post("/cleanup")
async def cleanup_scraper():
    """Clean up scraper resources."""
    global scraper
    if scraper:
        try:
            await scraper.cleanup()
            return {"status": "success", "message": "Scraper cleaned up successfully"}
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "message": "No scraper instance to clean up"}

@app.post("/force-cleanup")
async def force_cleanup_scraper():
    """Force cleanup of all scraper resources."""
    global scraper
    if scraper:
        try:
            await scraper.force_cleanup()
            scraper = None
            return {"status": "success", "message": "Scraper force cleaned up successfully"}
        except Exception as e:
            logger.error(f"Force cleanup error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success", "message": "No scraper instance to clean up"}

@app.get("/scraping-status", response_model=ScrapingStatus)
async def get_scraping_status():
    """Get information about the last scraping run and next scheduled run."""
    try:
        # Get next scheduled run time
        next_run = None
        for job in scheduler.get_jobs():
            if job.next_run_time:
                if next_run is None or job.next_run_time < next_run:
                    next_run = job.next_run_time

        return ScrapingStatus(
            last_successful_scrape=last_successful_scrape,
            total_articles=len(all_articles),
            new_articles_since_last_scrape=len([a for a in all_articles if a.get('scraped_at') == last_successful_scrape]),
            next_scheduled_scrape=next_run.isoformat() if next_run else None,
            last_scrape_error=last_scrape_error
        )
    except Exception as e:
        logger.error(f"Error getting scraping status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/all-articles", response_model=ArticleList)
async def get_all_articles():
    """Get all articles that have been scraped."""
    try:
        return ArticleList(
            articles=all_articles,
            total_count=len(all_articles),
            last_updated=last_successful_scrape or datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting all articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles", response_model=List[Article])
async def get_articles():
    """Get list of articles from FT"""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Define World section and its subnavs
        world_sections = [
            "https://www.ft.com/world",
            "https://www.ft.com/world/middle-east",
            "https://www.ft.com/world/global-economy",
            "https://www.ft.com/world/uk",
            "https://www.ft.com/world/us",
            "https://www.ft.com/world/asia-pacific",
            "https://www.ft.com/world/africa",
            "https://www.ft.com/world/americas",
            "https://www.ft.com/world/europe",
            "https://www.ft.com/world/emerging-markets",
            "https://www.ft.com/world/middle-east-north-africa",
            "https://www.ft.com/world/ukraine"
        ]

        new_articles = []
        for i, section in enumerate(world_sections, 1):
            try:
                logger.info(f"Scraping section {i}/{len(world_sections)}: {section}")
                scraper.driver.get(section)
                time.sleep(2)  # Allow dynamic content to load

                # Scroll to load more content
                for scroll in range(3):  # Scroll 3 times
                    logger.info(f"Scrolling page {scroll + 1}/3")
                    scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)  # Wait for content to load

                # Wait for articles to load
                logger.info("Waiting for articles to load...")
                articles = WebDriverWait(scraper.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article, .js-teaser, .o-teaser, .o-teaser--standard, .o-teaser--hero, .o-teaser--top-story"))
                )
                logger.info(f"Found {len(articles)} articles in {section}")

                for article in articles:
                    try:
                        # Try different selectors for headline
                        headline = None
                        for selector in [
                            "h3", 
                            ".o-teaser__heading", 
                            ".js-teaser-heading-link",
                            ".o-teaser__heading a",
                            "a[data-trackable='headline']",
                            ".o-teaser__title"
                        ]:
                            try:
                                headline = article.find_element(By.CSS_SELECTOR, selector).text
                                if headline:
                                    # Clean up encoding issues
                                    headline = headline.encode('ascii', 'ignore').decode('ascii')
                                    logger.info(f"Found headline with selector {selector}: {headline}")
                                    break
                            except Exception as e:
                                logger.debug(f"Failed to find headline with selector {selector}: {str(e)}")
                                continue

                        if not headline:
                            logger.warning("No headline found for article")
                            continue

                        # Get URL
                        try:
                            # Try different selectors for URL
                            url = None
                            for selector in ["a", "a[data-trackable='headline']", ".o-teaser__heading a"]:
                                try:
                                    url = article.find_element(By.CSS_SELECTOR, selector).get_attribute("href")
                                    if url:
                                        break
                                except:
                                    continue

                            if not url:
                                logger.warning("No URL found for article")
                                continue

                            logger.info(f"Found URL: {url}")
                            if url in scraper.visited_urls:
                                logger.info(f"Skipping duplicate URL: {url}")
                                continue
                        except Exception as e:
                            logger.warning(f"Failed to get URL: {str(e)}")
                            continue

                        # Get standfirst/description
                        standfirst = ""
                        for selector in [
                            ".o-teaser__standfirst", 
                            ".js-teaser-standfirst", 
                            "p",
                            ".o-teaser__summary",
                            ".o-teaser__description"
                        ]:
                            try:
                                standfirst = article.find_element(By.CSS_SELECTOR, selector).text
                                if standfirst:
                                    # Clean up encoding issues
                                    standfirst = standfirst.encode('ascii', 'ignore').decode('ascii')
                                    logger.info(f"Found standfirst with selector {selector}")
                                    break
                            except Exception as e:
                                logger.debug(f"Failed to find standfirst with selector {selector}: {str(e)}")
                                continue

                        # Get timestamp if available
                        timestamp = ""
                        try:
                            time_elem = article.find_element(By.CSS_SELECTOR, "time")
                            timestamp = time_elem.get_attribute("datetime")
                            logger.info(f"Found timestamp: {timestamp}")
                        except Exception as e:
                            logger.debug(f"Failed to get timestamp: {str(e)}")

                        article_data = Article(
                            headline=headline,
                            url=url,
                            standfirst=standfirst,
                            date=timestamp,
                            tags=[section.split("/")[-1]]  # Use section as tag
                        )

                        new_articles.append(article_data)
                        scraper.visited_urls.add(url)
                        logger.info(f"Added article: {headline}")

                    except Exception as e:
                        logger.error(f"Error processing article preview: {str(e)}")
                        continue

                logger.info(f"Finished scraping section {i}/{len(world_sections)}: {section}")

            except Exception as e:
                logger.error(f"Error scraping section {section}: {str(e)}")
                continue

        # Save progress
        scraper._save_visited_urls()
        logger.info(f"Total new articles found: {len(new_articles)}")
        return new_articles

    except Exception as e:
        logger.error(f"Error getting articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/article/{url:path}", response_model=Article)
async def get_article(url: str):
    """Get full article content"""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Refresh session if needed
        scraper.refresh_session_if_needed()
        
        # Get full article content
        article_data = scraper.scrape_full_article(url)
        if not article_data:
            raise HTTPException(status_code=404, detail="Article not found")
            
        return article_data
    except Exception as e:
        logger.error(f"Error getting article: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/prioritized-articles", response_model=List[PrioritizedArticle])
async def get_prioritized_articles():
    """Get a prioritized list of articles for the iOS app."""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Get all articles
        articles = await get_articles()
        if not articles:
            return []

        # Prioritize articles
        prioritized = prioritizer.prioritize_articles(articles)
        
        # Convert to PrioritizedArticle format
        prioritized_articles = []
        for article in prioritized:
            prioritized_article = PrioritizedArticle(
                **article.dict(),
                summary=None,
                audio_url=None,
                processing_status="pending"
            )
            prioritized_articles.append(prioritized_article)

        return prioritized_articles

    except Exception as e:
        logger.error(f"Error getting prioritized articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update-article-status")
async def update_article_status(article_url: str, status: str, summary: Optional[str] = None, audio_url: Optional[str] = None):
    """Update the processing status of an article."""
    try:
        # In a real implementation, you would store this in a database
        # For now, we'll just log it
        logger.info(f"Article {article_url} status updated to {status}")
        if summary:
            logger.info(f"Summary: {summary}")
        if audio_url:
            logger.info(f"Audio URL: {audio_url}")
        
        return {"status": "success", "message": "Article status updated"}
    except Exception as e:
        logger.error(f"Error updating article status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Initialize services and start scheduler on startup."""
    global scraper, scheduler
    try:
        # Initialize scraper
        scraper = FTScraper()
        await scraper.initialize()
        logger.info("Scraper initialized on startup")

        # Configure scheduler
        scheduler.add_job(
            scheduled_scraping,
            CronTrigger(hour='6', minute='0'),  # 6 AM
            id='morning_scrape',
            name='Morning scraping at 6 AM'
        )
        scheduler.add_job(
            scheduled_scraping,
            CronTrigger(hour='12', minute='0'),  # 12 PM
            id='noon_scrape',
            name='Noon scraping at 12 PM'
        )
        scheduler.add_job(
            scheduled_scraping,
            CronTrigger(hour='19', minute='0'),  # 7 PM
            id='evening_scrape',
            name='Evening scraping at 7 PM'
        )

        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler started with 3 daily scraping jobs")

    except Exception as e:
        logger.error(f"Failed to initialize services on startup: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global scraper, scheduler
    try:
        # Shutdown scheduler
        scheduler.shutdown()
        logger.info("Scheduler shut down")

        # Cleanup scraper
        if scraper:
            await scraper.cleanup()
            logger.info("Scraper cleaned up on shutdown")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)