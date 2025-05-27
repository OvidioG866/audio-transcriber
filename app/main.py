import os
import logging
import gc
import torch
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from app.services.scraper import FTScraper
from app.services.audio_generator import AudioGenerator
from app.services.article_prioritizer import ArticlePrioritizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="FT Article Audio Generator")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
scraper = None
audio_generator = AudioGenerator()
article_prioritizer = ArticlePrioritizer()

# Configure memory management
def configure_memory():
    # Clear CUDA cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Force garbage collection
    gc.collect()

@app.on_event("startup")
async def startup_event():
    configure_memory()

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
    audio_path: Optional[str] = None

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

@app.post("/generate-audio/{url:path}")
async def generate_audio(url: str, background_tasks: BackgroundTasks):
    """Generate audio for an article"""
    if not scraper:
        raise HTTPException(status_code=400, detail="Scraper not initialized")
    
    try:
        # Get article content
        article_data = await get_article(url)
        
        # Calculate priority score
        priority_score = article_prioritizer.calculate_priority_score(article_data)
        article_data['priority_score'] = priority_score
        
        # Generate audio in background
        def generate_audio_task():
            audio_path = audio_generator.generate_article_audio(article_data)
            if audio_path:
                article_data['audio_path'] = audio_path
        
        background_tasks.add_task(generate_audio_task)
        
        return {
            "message": "Audio generation started",
            "article": article_data
        }
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
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
        prioritized_articles = article_prioritizer.prioritize_articles(full_articles)
        
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
    configure_memory()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 