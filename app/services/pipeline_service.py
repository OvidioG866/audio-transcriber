from typing import List, Optional
import os
import asyncio
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from app.models.article import Article
from app.services.scraper_service import FTScraper
from app.services.prioritizator_service import GeopoliticalPrioritizer
from app.services.tts_service import UnrealSpeechTTS
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

class PipelineService:
    def __init__(self, db: Session):
        self.db = db
        self.scraper = None
        self.prioritizer = GeopoliticalPrioritizer()
        self.tts = UnrealSpeechTTS()
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        os.makedirs(settings.AUDIO_STORAGE_PATH, exist_ok=True)
        os.makedirs(settings.ARTICLE_STORAGE_PATH, exist_ok=True)
        os.makedirs(settings.PRIORITY_STORAGE_PATH, exist_ok=True)

    async def initialize_scraper(self):
        """Initialize the scraper with credentials"""
        if not self.scraper:
            self.scraper = FTScraper(
                username=settings.FT_USERNAME,
                uni_id=settings.FT_UNI_ID,
                password=settings.FT_PASSWORD
            )
            await self.scraper.initialize()

    async def scrape_articles(self) -> List[Article]:
        """Scrape articles from FT"""
        await self.initialize_scraper()
        previews = await self.scraper.scrape_articles()
        
        articles = []
        for preview in previews:
            article = Article(
                title=preview['headline'],
                url=preview['url'],
                summary=preview.get('standfirst'),
                safe_title=self._create_safe_title(preview['headline'])
            )
            self.db.add(article)
            articles.append(article)
        
        self.db.commit()
        return articles

    async def process_article(self, article: Article) -> bool:
        """Process a single article: scrape content and generate audio"""
        try:
            # Scrape full content
            article_data = await self.scraper.scrape_full_article(article.url)
            if not article_data or not article_data.get('full_text'):
                return False

            # Update article with full content
            article.content = article_data['full_text']
            article.date = article_data.get('date')
            article.author = article_data.get('author')
            
            # Generate script
            script = await self._generate_script(article)
            if not script:
                return False

            # Save script
            script_path = os.path.join(settings.ARTICLE_STORAGE_PATH, f"script_{article.safe_title}.txt")
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script)
            article.script_path = script_path

            # Generate audio
            audio_path = os.path.join(settings.AUDIO_STORAGE_PATH, f"audio_{article.safe_title}.mp3")
            success = await self.tts.generate_audio(
                text=script,
                output_path=audio_path,
                voice_id="Sierra"
            )
            
            if success:
                article.audio_path = audio_path
                article.is_audio_generated = True
            
            article.is_processed = True
            self.db.commit()
            return success

        except Exception as e:
            logger.error(f"Error processing article {article.title}: {str(e)}")
            return False

    async def prioritize_articles(self) -> List[Article]:
        """Prioritize articles based on geopolitical relevance"""
        articles = self.db.query(Article).filter(Article.is_processed == True).all()
        prioritized = self.prioritizer.prioritize_articles(articles)
        
        # Update scores in database
        for article in prioritized:
            article.score = article.score
        self.db.commit()
        
        return prioritized

    def get_article(self, article_id: int) -> Optional[Article]:
        """Get article by ID"""
        return self.db.query(Article).filter(Article.id == article_id).first()

    def get_articles(self) -> List[Article]:
        """Get all articles"""
        return self.db.query(Article).all()

    def get_article_status(self, article: Article) -> dict:
        """Get the status of an article"""
        return {
            "id": article.id,
            "title": article.title,
            "is_processed": article.is_processed,
            "is_audio_generated": article.is_audio_generated,
            "score": article.score,
            "audio_path": article.audio_path
        }

    def _create_safe_title(self, title: str) -> str:
        """Create a safe filename from title"""
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return safe_title[:50]  # Limit length

    async def _generate_script(self, article: Article) -> Optional[str]:
        """Generate podcast script from article content"""
        try:
            from app.services.openai_service import generate_podcast_script
            return await generate_podcast_script(
                title=article.title,
                content=article.content
            )
        except Exception as e:
            logger.error(f"Error generating script: {str(e)}")
            return None 