import os
import time
from scraper import FTScraper, setup_logging
from prioritizator import GeopoliticalPrioritizer, read_articles_from_folder
from openAI import generate_podcast_script
from unrealspeech_tts import UnrealSpeechTTS  # Import UnrealSpeech instead of ElevenLabs
import logging
from datetime import datetime
import pygame
from typing import Optional
import threading

# Setup logging with rotation
setup_logging()
logger = logging.getLogger(__name__)

# Initialize pygame mixer
pygame.mixer.init()

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

        # Save prioritization order to a text file
        try:
            # Create a dedicated directory for priority lists
            priority_dir = "priority_lists"
            os.makedirs(priority_dir, exist_ok=True)
            
            # Delete old priority list files
            for old_file in os.listdir(priority_dir):
                if old_file.startswith('article_priority_'):
                    try:
                        os.remove(os.path.join(priority_dir, old_file))
                        logger.info(f"Deleted old priority list: {old_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old priority list {old_file}: {str(e)}")
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            priority_file = os.path.join(priority_dir, f"article_priority_{timestamp}.txt")
            
            with open(priority_file, 'w', encoding='utf-8') as f:
                f.write(f"Article Prioritization Order - Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                
                for i, article in enumerate(self.ranked_articles, 1):
                    f.write(f"{i}. Score: {article.score:.2f}\n")
                    f.write(f"   Title: {article.title}\n")
                    if hasattr(article, 'url') and article.url:
                        f.write(f"   URL: {article.url}\n")
                    if hasattr(article, 'summary') and article.summary:
                        f.write(f"   Summary: {article.summary}\n")
                    f.write("\n" + "-"*80 + "\n\n")
            
            logger.info(f"Saved detailed prioritization order to: {os.path.abspath(priority_file)}")
            
            # Delete old simple priority list if it exists
            simple_list_file = "current_priority_list.txt"
            if os.path.exists(simple_list_file):
                try:
                    os.remove(simple_list_file)
                    logger.info(f"Deleted old simple priority list")
                except Exception as e:
                    logger.warning(f"Failed to delete old simple priority list: {str(e)}")
            
            # Save the simple list in the root directory for easy access
            with open(simple_list_file, 'w', encoding='utf-8') as f:
                f.write(f"Current Article Priority List - Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                for i, article in enumerate(self.ranked_articles, 1):
                    f.write(f"{i}. {article.title}\n")
            
            logger.info(f"Saved simple priority list to: {os.path.abspath(simple_list_file)}")
            print(f"\nPriority list has been saved to: {os.path.abspath(simple_list_file)}")
            
            # Print the full list to console
            print("\nFull Article Priority List:")
            print("="*80)
            for i, article in enumerate(self.ranked_articles, 1):
                print(f"{i}. {article.title}")
            print("="*80)
            
        except Exception as e:
            logger.error(f"Failed to save prioritization order: {str(e)}")
            raise  # Re-raise the exception to see the full error

    def _process_article(self, index, is_initial_scrape=False):
        """Process a single article: generate script and audio"""
        if index >= len(self.ranked_articles):
            logger.info("No more articles to process")
            return False

        article = self.ranked_articles[index]
        logger.info(f"\nProcessing article {index + 1}/{len(self.ranked_articles)}")
        logger.info(f"Title: {article.title}")
        logger.info(f"Priority Score: {article.score:.2f}")

        # Create safe filename from article title
        safe_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Limit length
        
        script_path = os.path.join(self.output_dir, f"script_{safe_title}.txt")
        audio_path = os.path.join(self.audio_dir, f"audio_{safe_title}.mp3")
        
        # Always scrape full content for the next article in priority
        if not os.path.exists(script_path):
            if not article.url:
                logger.error(f"No URL found for article: {article.title}")
                return False
                
            logger.info("Scraping full article content...")
            
            # Initialize scraper if not already done
            if not self.scraper:
                username = os.getenv("FT_USERNAME")
                uni_id = os.getenv("FT_UNI_ID")
                password = os.getenv("FT_PASSWORD")

                if not all([username, uni_id, password]):
                    logger.error("Missing FT credentials in environment variables")
                    return False

                logger.info("Initializing scraper...")
                self.scraper = FTScraper(username, uni_id, password)
            
            # Add retry logic for article scraping
            max_retries = 3
            retry_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Ensure we're logged in before scraping
                    if not self.scraper.is_logged_in:
                        logger.info("Session expired, logging in again...")
                        if not self.scraper.login():
                            logger.error("Failed to login")
                            return False
                    
                    article_data = self.scraper.scrape_full_article(article.url, is_initial_scrape)
                    if article_data and article_data.get('full_text'):
                        # Generate script from article content
                        script = generate_podcast_script(
                            title=article_data['title'],
                            content=article_data['full_text']
                        )
                        
                        # Save script
                        try:
                            with open(script_path, 'w', encoding='utf-8') as f:
                                f.write(script)
                            logger.info(f"Saved script to: {script_path}")
                            break  # Success, exit retry loop
                        except Exception as e:
                            logger.error(f"Failed to save script: {str(e)}")
                            return False
                    else:
                        if attempt < max_retries - 1:
                            logger.warning(f"Failed to get article content (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            logger.error("Failed to get article content after all retries")
                            return False
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Error scraping article (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to scrape article after all retries: {str(e)}")
                        return False
        else:
            # Read existing script
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script = f.read()
                logger.info(f"Read existing script from: {script_path}")
            except Exception as e:
                logger.error(f"Failed to read script file: {str(e)}")
                return False

        # Generate audio only if it doesn't exist
        if not os.path.exists(audio_path):
            logger.info("Generating audio...")
            start_time = time.time()

            # Check if UnrealSpeech API key is available
            if not os.getenv("UNREALSPEECH_API_KEY"):
                logger.warning("UNREALSPEECH_API_KEY not found in environment variables")
                logger.info("Skipping audio generation - please set your API key")
                return True

            try:
                # Use UnrealSpeech TTS to generate audio
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
            except Exception as e:
                logger.error(f"Audio generation failed: {str(e)}")
                return False
        else:
            logger.info(f"Audio file already exists at {audio_path}, skipping generation")
            return True

    def generate_initial_content(self):
        """Step 3: Generate initial content (first 3 articles)"""
        logger.info("="*50)
        logger.info("STEP 3: Generating initial content...")
        logger.info("="*50)

        # Process only the top 3 articles
        num_articles = min(3, len(self.ranked_articles))
        logger.info(f"Will process {num_articles} articles")

        for i in range(num_articles):
            logger.info(f"\nProcessing article {i + 1}/{num_articles}")
            self._process_article(i, is_initial_scrape=True)

        logger.info("="*50)
        logger.info("Initial content generation completed")
        logger.info("="*50)

    def play_audio(self, index):
        """Play the audio for a specific article"""
        if self.is_playing and not self.is_paused:
            logger.info("Already playing audio, please stop current playback first")
            return False

        # Ensure index is at least 0 and within bounds
        if index < 0 or index >= len(self.ranked_articles):
            logger.error(f"Invalid article index. Must be between 0 and {len(self.ranked_articles) - 1}")
            return False

        # Get the article and create safe filename
        article = self.ranked_articles[index]
        safe_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Limit length
        audio_path = os.path.join(self.audio_dir, f"audio_{safe_title}.mp3")

        if os.path.exists(audio_path):
            logger.info(f"Playing audio for article: {article.title}")
            try:
                # If we're resuming from a pause, don't stop current audio
                if not self.is_paused:
                    pygame.mixer.music.stop()
                    self.pause_position = 0

                # Load and play the new audio
                pygame.mixer.music.load(audio_path)
                if self.is_paused:
                    pygame.mixer.music.play(start=self.pause_position)
                    self.is_paused = False
                else:
                    pygame.mixer.music.play()
                
                self.is_playing = True
                self.current_audio_index = index

                # Instead of blocking, return True to indicate playback started
                return True
            except Exception as e:
                logger.error(f"Error playing audio: {str(e)}")
                self.is_playing = False
                return False
        else:
            logger.error(f"Audio file not found: {audio_path}")
            return False

    def pause_audio(self):
        """Pause the current audio playback"""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.pause_position = pygame.mixer.music.get_pos() / 1000.0  # Convert to seconds
            logger.info("Audio playback paused")
            return True
        return False

    def resume_audio(self):
        """Resume the current audio playback from where it was paused"""
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            logger.info("Audio playback resumed")
            return True
        return False

    def stop_audio(self):
        """Stop current audio playback"""
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False
            self.is_paused = False
            self.pause_position = 0
            logger.info("Audio playback stopped")
            return True
        return False

    def play_next(self):
        """Skip current article, play next one, and generate audio for the following unconverted article"""
        if self.current_audio_index + 1 < len(self.ranked_articles):
            # Stop current playback if any
            if self.is_playing:
                self.stop_audio()
            
            # Play next audio
            next_index = self.current_audio_index + 1
            if self.play_audio(next_index):
                # Find next unconverted article
                for i in range(next_index + 1, len(self.ranked_articles)):
                    article = self.ranked_articles[i]
                    safe_title = "".join(c for c in article.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    safe_title = safe_title[:50]  # Limit length
                    audio_path = os.path.join(self.audio_dir, f"audio_{safe_title}.mp3")
                    
                    if not os.path.exists(audio_path):
                        logger.info("\n" + "="*50)
                        logger.info(f"Starting background generation for article {i + 1}:")
                        logger.info(f"Title: {article.title}")
                        logger.info("="*50 + "\n")
                        
                        # Start background generation in a separate thread
                        def background_generation():
                            try:
                                success = self._process_article(i, is_initial_scrape=False)
                                if success:
                                    logger.info("\n" + "="*50)
                                    logger.info(f"Successfully generated audio for article {i + 1}:")
                                    logger.info(f"Title: {article.title}")
                                    logger.info("="*50 + "\n")
                                else:
                                    logger.error("\n" + "="*50)
                                    logger.error(f"Failed to generate audio for article {i + 1}:")
                                    logger.error(f"Title: {article.title}")
                                    logger.error("="*50 + "\n")
                            except Exception as e:
                                logger.error(f"Error during background generation: {str(e)}")
                        
                        # Start the background thread
                        thread = threading.Thread(target=background_generation)
                        thread.daemon = True  # Thread will be killed when main program exits
                        thread.start()
                        break
                return True
        else:
            logger.info("No more articles to play")
        return False

    def get_current_status(self):
        """Get current pipeline status"""
        status = {
            "current_article_index": self.current_article_index,
            "total_articles": len(self.ranked_articles),
            "is_playing": self.is_playing,
            "current_audio_index": self.current_audio_index
        }
        return status

    def process_next_article(self) -> bool:
        """Process the next article in the queue"""
        if self.current_article_index >= len(self.ranked_articles):
            logger.info("No more articles to process")
            return False

        logger.info(f"\nProcessing next article (index: {self.current_article_index + 1})")
        success = self._process_article(self.current_article_index, is_initial_scrape=False)
        if success:
            self.current_article_index += 1
            logger.info(f"Successfully processed article {self.current_article_index}")
            return True
        logger.error(f"Failed to process article {self.current_article_index + 1}")
        return False

    def get_remaining_articles(self):
        """Show remaining articles"""
        if not self.ranked_articles:
            logger.info("No articles available")
            return

        logger.info("\nRemaining articles:")
        for i, article in enumerate(self.ranked_articles[self.current_article_index:], self.current_article_index + 1):
            logger.info(f"{i}. {article.title}")

def print_help():
    """Print available commands"""
    print("\nAvailable commands:")
    print("  next    - Play next article's audio and start generating the following one")
    print("  play    - Play the first article's audio")
    print("  play N  - Play audio for article N (e.g., 'play 1' for first article)")
    print("  pause   - Pause current audio playback")
    print("  resume  - Resume audio playback from where it was paused")
    print("  stop    - Stop current audio playback")
    print("  list    - Show remaining articles")
    print("  help    - Show this help message")
    print("  exit    - Exit the program")

def main():
    try:
        logger.info("\n" + "="*50)
        logger.info("Starting News Pipeline")
        logger.info("="*50)

        # Check for UnrealSpeech API key
        if not os.getenv("UNREALSPEECH_API_KEY"):
            logger.warning("UNREALSPEECH_API_KEY not found in environment variables")
            logger.warning("Audio generation will be skipped")
            print("\n⚠️  WARNING: UnrealSpeech API key not found!")
            print("Set UNREALSPEECH_API_KEY environment variable to enable audio generation")
            print("The pipeline will continue but skip audio generation steps.\n")

        # Initialize pipeline
        pipeline = NewsPipeline()

        try:
            # Step 1: Scrape articles
            try:
                pipeline.scrape_articles()
            except Exception as e:
                logger.error(f"Scraping failed: {str(e)}")
                return

            # Step 2: Prioritize articles
            try:
                pipeline.prioritize_articles()
            except Exception as e:
                logger.error(f"Prioritization failed: {str(e)}")
                return

            # Step 3: Generate initial content
            try:
                pipeline.generate_initial_content()
            except Exception as e:
                logger.error(f"Content generation failed: {str(e)}")
                return

            logger.info("\n" + "="*50)
            logger.info("Initial pipeline setup completed")
            logger.info("="*50)

            print_help()

            while True:
                try:
                    command = input("\nEnter command (or 'help' for options): ").strip().lower()

                    if command == 'exit':
                        logger.info("Exiting program")
                        break
                    elif command == 'next':
                        pipeline.play_next()
                    elif command == 'list':
                        pipeline.get_remaining_articles()
                    elif command == 'play':
                        # Play the first article's audio
                        pipeline.play_audio(0)
                    elif command == 'stop':
                        pipeline.stop_audio()
                    elif command == 'pause':
                        pipeline.pause_audio()
                    elif command == 'resume':
                        pipeline.resume_audio()
                    elif command.startswith('play '):
                        try:
                            # Extract article number from command
                            article_num = int(command.split()[1]) - 1  # Convert to 0-based index
                            if 0 <= article_num < len(pipeline.ranked_articles):
                                pipeline.play_audio(article_num)
                            else:
                                logger.error(f"Invalid article number. Must be between 1 and {len(pipeline.ranked_articles)}")
                        except ValueError:
                            logger.error("Invalid article number. Use 'play N' where N is the article number")
                    elif command == 'help':
                        print_help()
                    else:
                        logger.info("Unknown command. Type 'help' for available commands.")

                except KeyboardInterrupt:
                    logger.info("\nReceived keyboard interrupt. Type 'exit' to quit.")
                except Exception as e:
                    logger.error(f"Error processing command: {str(e)}")

        finally:
            # Clean up resources but keep the session alive
            pipeline.cleanup()

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise
    finally:
        # Clean up pygame
        pygame.mixer.quit()

if __name__ == "__main__":
    main()