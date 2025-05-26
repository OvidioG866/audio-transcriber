from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import aiofiles
import os
from sqlalchemy.orm import Session

from app.services.pipeline_service import PipelineService
from app.core.database import get_db
from app.core.config import Settings

router = APIRouter()
settings = Settings()

@router.get("/{article_id}/stream")
async def stream_audio(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Stream audio for a specific article"""
    pipeline = PipelineService(db)
    article = pipeline.get_article(article_id)
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if not article.audio_path or not os.path.exists(article.audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    async def audio_stream():
        async with aiofiles.open(article.audio_path, 'rb') as f:
            while chunk := await f.read(8192):  # 8KB chunks
                yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="audio_{article.safe_title}.mp3"'
        }
    ) 