import os
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from datetime import datetime

from scraper import FTScraper
from prioritizator import GeopoliticalPrioritizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="FT Article Scraper")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
scraper = None
prioritizer = GeopoliticalPrioritizer()

# Models
class ScraperConfig(BaseModel):
    username: str
    uni_id: str
    password: str

class Article(BaseModel):
    headline: str
    url: str
    standfirst: Optional[str] = None
    full_text: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    priority_score: Optional[float] = None
    tags: Optional[List[str]] = None

# Routes
@app.post("/initialize")
async def initialize_scraper(config: ScraperConfig):
    """Initialize the FT scraper with credentials"""
    global scraper
    try:
        scraper = FTScraper(
            username=config.username,
            uni_id=config.uni_id,
            password=config.password
        )
        success = scraper.login()
        if not success:
            raise HTTPException(status_code=401, detail="Failed to login to FT")
        return {"message": "Scraper initialized successfully"}
    except Exception as e:
        logger.error(f"Error initializing scraper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles", response_model=List[Article])
async def get_articles():
    """Get list of articles from FT"""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Refresh session if needed
        scraper.refresh_session_if_needed()
        
        # Get article previews
        articles = scraper.scrape_articles()
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found")
            
        return articles
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

@app.get("/prioritize-articles", response_model=List[Article])
async def prioritize_articles():
    """Get prioritized list of articles"""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Get articles
        articles = await get_articles()
        
        # Get full content for each article
        full_articles = []
        for article in articles:
            try:
                full_article = await get_article(article['url'])
                full_articles.append(full_article)
            except Exception as e:
                logger.error(f"Error getting full article: {str(e)}")
                continue
        
        # Prioritize articles
        prioritized_articles = prioritizer.prioritize_articles(full_articles)
        
        return prioritized_articles
    except Exception as e:
        logger.error(f"Error prioritizing articles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global scraper
    if scraper:
        scraper.force_cleanup()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)