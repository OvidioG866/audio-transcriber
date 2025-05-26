from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.services.pipeline_service import PipelineService
from app.core.database import get_db
from app.models.article import Article

router = APIRouter()

@router.get("/", response_model=List[dict])
async def get_articles(
    db: Session = Depends(get_db)
):
    """Get all articles"""
    pipeline = PipelineService(db)
    articles = pipeline.get_articles()
    return [pipeline.get_article_status(article) for article in articles]

@router.get("/{article_id}", response_model=dict)
async def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Get article by ID"""
    pipeline = PipelineService(db)
    article = pipeline.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return pipeline.get_article_status(article)

@router.post("/{article_id}/process")
async def process_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process article in background"""
    pipeline = PipelineService(db)
    article = pipeline.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    background_tasks.add_task(pipeline.process_article, article)
    return {"message": "Article processing started", "article_id": article_id}

@router.post("/scrape")
async def scrape_articles(
    db: Session = Depends(get_db)
):
    """Scrape new articles from FT"""
    pipeline = PipelineService(db)
    articles = await pipeline.scrape_articles()
    return {"message": f"Scraped {len(articles)} articles", "articles": articles}

@router.post("/prioritize")
async def prioritize_articles(
    db: Session = Depends(get_db)
):
    """Prioritize all articles"""
    pipeline = PipelineService(db)
    articles = await pipeline.prioritize_articles()
    return {"message": f"Prioritized {len(articles)} articles", "articles": articles} 