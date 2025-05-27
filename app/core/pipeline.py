import os
import time
from datetime import datetime
import logging
import threading
from typing import Optional

from app.services.scraper import FTScraper
from app.services.prioritizator import GeopoliticalPrioritizer, read_articles_from_folder
from app.services.openai_service import generate_podcast_script
from app.services.tts import UnrealSpeechTTS

logger = logging.getLogger(__name__)

class NewsPipeline:
    def __init__(self):
        self.scraper = None
        self.prioritizer = GeopoliticalPrioritizer()
        self.current_article_index = 0
        self.articles = []
        self.ranked_articles = []
        self.output_dir = "scraped_articles"
        self.audio_dir = "audio_outputs"
        self.tts = UnrealSpeechTTS()
        self.is_playing = False
        self.is_paused = False
        self.current_audio_index = -1
        self.pause_position = 0
        self.last_login_file = "last_login.txt"

        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        # Initialize scraper with persistent session
        self._initialize_scraper()

        logger.info("Pipeline initialized")
        logger.info(f"Output directory: {os.path.abspath(self.output_dir)}")
        logger.info(f"Audio directory: {os.path.abspath(self.audio_dir)}")

    def _initialize_scraper(self):
        """Initialize the scraper with persistent session."""
        username = os.getenv("FT_USERNAME")
        uni_id = os.getenv("FT_UNI_ID")
        password = os.getenv("FT_PASSWORD")

        if not all([username, uni_id, password]):
            raise ValueError("Missing FT credentials in environment variables")

        logger.info("Initializing scraper with persistent session...")
        self.scraper = FTScraper(username, uni_id, password)

    def cleanup(self):
        """Clean up resources but keep the session alive."""
        if self.scraper:
            self.scraper.cleanup()

    def force_cleanup(self):
        """Force cleanup of all resources including the browser."""
        if self.scraper:
            self.scraper.force_cleanup()

    def _get_last_login_time(self) -> Optional[datetime]:
        """Get the last login time from the file"""
        try:
            if os.path.exists(self.last_login_file):
                with open(self.last_login_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.error(f"Error reading last login time: {str(e)}")
        return None

    def _update_last_login_time(self):
        """Update the last login time in the file"""
        try:
            with open(self.last_login_file, 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            logger.error(f"Error updating last login time: {str(e)}")

    def _should_skip_scraping(self) -> bool:
        """Check if we should skip scraping based on last login time"""
        last_login = self._get_last_login_time()
        if last_login:
            time_since_login = datetime.now() - last_login
            if time_since_login.total_seconds() < 3600:  # Less than 1 hour
                logger.info(f"Last login was {time_since_login.total_seconds()/60:.1f} minutes ago, skipping scraping")
                return True
        return False

    def scrape_articles(self):
        """Step 1: Scrape articles from FT"""
        logger.info("="*50)
        logger.info("STEP 1: Starting article scraping...")
        logger.info("="*50)

        # Check if we should skip scraping
        if self._should_skip_scraping():
            logger.info("Skipping article scraping due to recent login")
            return

        # Refresh session if needed
        if not self.scraper.refresh_session_if_needed():
            logger.error("Failed to refresh session")
            return

        start_time = time.time()
        previews = self.scraper.scrape_articles()
        end_time = time.time()

        if not previews:
            raise ValueError("No article previews were scraped successfully")

        logger.info(f"Successfully scraped {len(previews)} article previews")
        logger.info(f"Article scraping completed in {end_time - start_time:.2f} seconds")
        logger.info("="*50)

        # Update last login time
        self._update_last_login_time()

        # Save previews to files
        for i, preview in enumerate(previews, 1):
            logger.info(f"Processing preview {i} of {len(previews)}")
            safe_title = "".join(c for c in preview['headline'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = os.path.join(self.output_dir, f"article_{i}_{safe_title[:50]}.txt")
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {preview['headline']}\n")
                    f.write(f"URL: {preview['url']}\n")
                    if preview['standfirst']:
                        f.write(f"Summary: {preview['standfirst']}\n")
                    f.write("\n" + "="*50 + "\n\n")
                logger.info(f"Saved preview to: {filename}")
            except Exception as e:
                logger.error(f"Failed to save preview {i}: {str(e)}")

        # Now fetch full content for each article
        for i, preview in enumerate(previews, 1):
            logger.info(f"Fetching full content for article {i} of {len(previews)}")
            try:
                full_article = self.scraper.scrape_full_article(preview['url'])
                if full_article:
                    # Update the file with full content
                    filename = os.path.join(self.output_dir, f"article_{i}_{safe_title[:50]}.txt")
                    with open(filename, 'a', encoding='utf-8') as f:
                        if full_article.get('date'):
                            f.write(f"Date: {full_article['date']}\n")
                        if full_article.get('author'):
                            f.write(f"Author: {full_article['author']}\n")
                        f.write("\n" + "="*50 + "\n\n")
                        f.write(full_article['full_text'])
                    logger.info(f"Updated article with full content: {filename}")
                else:
                    logger.warning(f"Could not fetch full content for article {i}")
            except Exception as e:
                logger.error(f"Failed to fetch full content for article {i}: {str(e)}")
                continue

    def prioritize_articles(self):
        """Step 2: Prioritize articles"""
        logger.info("="*50)
        logger.info("STEP 2: Starting article prioritization...")
        logger.info("="*50)

        self.articles = read_articles_from_folder(self.output_dir)
        if not self.articles:
            raise ValueError("No articles found to prioritize")

        # Filter out articles without titles
        self.articles = [article for article in self.articles if article.title.strip()]
        if not self.articles:
            raise ValueError("No valid articles found to prioritize (all articles missing titles)")

        logger.info(f"Found {len(self.articles)} articles to prioritize")

        start_time = time.time()
        self.ranked_articles = self.prioritizer.prioritize_articles(self.articles)
        end_time = time.time()

        logger.info(f"Prioritization completed in {end_time - start_time:.2f} seconds")
        logger.info("Top 3 articles by priority:")
        for i, article in enumerate(self.ranked_articles[:3], 1):
            logger.info(f"{i}. Score: {article.score:.2f} - {article.title[:100]}...")
        logger.info("="*50)

        return self.ranked_articles

    def get_articles(self):
        """Get list of available articles"""
        return self.ranked_articles

    def get_article(self, article_id: int):
        """Get a specific article by ID"""
        if 0 <= article_id < len(self.ranked_articles):
            return self.ranked_articles[article_id]
        return None

    def get_audio_path(self, article):
        """Get the audio file path for an article"""
        safe_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Limit length
        return os.path.join(self.audio_dir, f"audio_{safe_title}.mp3")

    def generate_audio(self, article):
        """Generate audio for an article"""
        try:
            safe_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Limit length
            
            script_path = os.path.join(self.output_dir, f"script_{safe_title}.txt")
            audio_path = os.path.join(self.audio_dir, f"audio_{safe_title}.mp3")
            
            # Generate script if it doesn't exist
            if not os.path.exists(script_path):
                script = generate_podcast_script(
                    title=article.title,
                    content=article.content
                )
                
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(script)
                logger.info(f"Saved script to: {script_path}")
            else:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script = f.read()
                logger.info(f"Read existing script from: {script_path}")

            # Generate audio if it doesn't exist
            if not os.path.exists(audio_path):
                logger.info("Generating audio...")
                start_time = time.time()

                output_path = self.tts.text_to_speech(
                    text=script,
                    voice_id="Sierra",
                    bitrate="192k",
                    speed=0.0,
                    pitch=1.0,
                    codec="libmp3lame",
                    output_filename=f"audio_{safe_title}.mp3",
                    output_dir=self.audio_dir
                )
                
                audio_time = time.time() - start_time
                logger.info(f"Audio generated in {audio_time:.2f} seconds")
                logger.info(f"Audio saved to: {output_path}")
                return True
            else:
                logger.info(f"Audio file already exists at {audio_path}")
                return True

        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return False

    def get_article_status(self, article):
        """Get the status of an article's audio generation"""
        audio_path = self.get_audio_path(article)
        return {
            "article_id": article.id if hasattr(article, 'id') else None,
            "title": article.title,
            "audio_exists": os.path.exists(audio_path),
            "audio_path": audio_path if os.path.exists(audio_path) else None
        } 