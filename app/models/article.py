from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    url = Column(String, unique=True, index=True)
    summary = Column(String, nullable=True)
    content = Column(String, nullable=True)
    date = Column(DateTime, nullable=True)
    author = Column(String, nullable=True)
    score = Column(Float, default=0.0)
    safe_title = Column(String, index=True)
    script_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    is_processed = Column(Boolean, default=False)
    is_audio_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 