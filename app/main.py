from fastapi import FastAPI, WebSocket, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import aiofiles
import os
from typing import List, Optional
import asyncio
from datetime import datetime

from app.core.pipeline import NewsPipeline
from app.api.routes import auth, articles, audio
from app.api.websockets import ConnectionManager
from app.config import Settings

app = FastAPI(title="AI Radio API")
settings = Settings()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
manager = ConnectionManager()

# Initialize pipeline
pipeline = NewsPipeline()

@app.on_event("startup")
async def startup_event():
    """Initialize necessary components on startup"""
    # Create required directories
    os.makedirs(settings.AUDIO_STORAGE_PATH, exist_ok=True)
    os.makedirs(settings.ARTICLE_STORAGE_PATH, exist_ok=True)
    os.makedirs(settings.PRIORITY_STORAGE_PATH, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "AI Radio API"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle WebSocket messages
            await manager.broadcast(f"Message: {data}")
    except Exception as e:
        manager.disconnect(websocket)

@app.get("/articles")
async def get_articles():
    """Get list of available articles"""
    return pipeline.get_articles()

@app.get("/articles/{article_id}/audio")
async def stream_audio(article_id: int):
    """Stream audio for a specific article"""
    try:
        article = pipeline.get_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        audio_path = pipeline.get_audio_path(article)
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="Audio file not found")

        async def audio_stream():
            async with aiofiles.open(audio_path, 'rb') as f:
                while chunk := await f.read(8192):  # 8KB chunks
                    yield chunk

        return StreamingResponse(
            audio_stream(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="audio_{article.safe_title}.mp3"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/articles/{article_id}/generate")
async def generate_audio(article_id: int, background_tasks: BackgroundTasks):
    """Generate audio for an article in the background"""
    try:
        article = pipeline.get_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Start background generation
        background_tasks.add_task(pipeline.generate_audio, article)
        
        return {"message": "Audio generation started", "article_id": article_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/articles/{article_id}/status")
async def get_article_status(article_id: int):
    """Get the status of an article's audio generation"""
    try:
        article = pipeline.get_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        status = pipeline.get_article_status(article)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(articles.router, prefix="/articles", tags=["articles"])
app.include_router(audio.router, prefix="/audio", tags=["audio"]) 