from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    UNREALSPEECH_API_KEY: str = os.getenv("UNREALSPEECH_API_KEY", "")

    # FT Credentials
    FT_USERNAME: str = os.getenv("FT_USERNAME", "")
    FT_UNI_ID: str = os.getenv("FT_UNI_ID", "")
    FT_PASSWORD: str = os.getenv("FT_PASSWORD", "")

    # Server Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ai_radio.db")

    # Storage
    AUDIO_STORAGE_PATH: str = os.getenv("AUDIO_STORAGE_PATH", "./audio_outputs")
    ARTICLE_STORAGE_PATH: str = os.getenv("ARTICLE_STORAGE_PATH", "./scraped_articles")
    PRIORITY_STORAGE_PATH: str = os.getenv("PRIORITY_STORAGE_PATH", "./priority_lists")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    class Config:
        env_file = ".env" 