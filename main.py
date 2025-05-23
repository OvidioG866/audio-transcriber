import os
import time
from scraper import FTScraper
from Prioritizator import GeopoliticalPrioritizer, read_articles_from_folder
from openAI import generate_podcast_script
from elevenlabs_tts import text_to_speech  # Only import the function we need
import logging
from datetime import datetime
import pygame

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Print to console
        logging.FileHandler(f'pipeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')  # Save to file
    ]
)
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

        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        logger.info("Pipeline initialized")
        logger.info(f"Output directory: {os.path.abspath(self.output_dir)}")
        logger.info(f"Audio directory: {os.path.abspath(self.audio_dir)}")

    def scrape_articles(self):
        """Step 1: Scrape articles from FT"""
        logger.info("="*50)
        logger.info("STEP 1: Starting article scraping...")
        logger.info("="*50)

        username = os.getenv("FT_USERNAME")
        uni_id = os.getenv("FT_UNI_ID")
        password = os.getenv("FT_PASSWORD")

        if not all([username, uni_id, password]):
            raise ValueError("Missing FT credentials in environment variables")

        logger.info("Credentials found, initializing scraper...")
        self.scraper = FTScraper(username, uni_id, password)

        start_time = time.time()
        self.scraper.scrape_articles()
        end_time = time.time()

        logger.info(f"Article scraping completed in {end_time - start_time:.2f} seconds")
        logger.info("="*50)

    def prioritize_articles(self):
        """Step 2: Prioritize articles"""
        logger.info("="*50)
        logger.info("STEP 2: Starting article prioritization...")
        logger.info("="*50)

        self.articles = read_articles_from_folder(self.output_dir)
        if not self.articles:
            raise ValueError("No articles found to prioritize")

        logger.info(f"Found {len(self.articles)} articles to prioritize")

        start_time = time.time()
        self.ranked_articles = self.prioritizer.prioritize_articles(self.articles)
        end_time = time.time()

        logger.info(f"Prioritization completed in {end_time - start_time:.2f} seconds")
        logger.info("Top 3 articles by priority:")
        for i, article in enumerate(self.ranked_articles[:3], 1):
            logger.info(f"{i}. Score: {article.score:.2f} - {article.title[:100]}...")
        logger.info("="*50)

    def generate_initial_content(self):
        """Step 3: Generate initial content (first 3 articles)"""
        logger.info("="*50)
        logger.info("STEP 3: Generating initial content...")
        logger.info("="*50)

        num_articles = min(3, len(self.ranked_articles))
        logger.info(f"Will process {num_articles} articles")

        for i in range(num_articles):
            logger.info(f"\nProcessing article {i + 1}/{num_articles}")
            self._process_article(i)

        logger.info("="*50)
        logger.info("Initial content generation completed")
        logger.info("="*50)

    def _process_article(self, index):
        """Process a single article: generate script and audio"""
        if index >= len(self.ranked_articles):
            logger.info("No more articles to process")
            return False

        article = self.ranked_articles[index]
        logger.info(f"\nProcessing article {index + 1}/{len(self.ranked_articles)}")
        logger.info(f"Title: {article.title}")
        logger.info(f"Priority Score: {article.score:.2f}")

        # Generate script
        logger.info("Generating podcast script...")
        start_time = time.time()
        script = generate_podcast_script(article.title, article.content)
        script_time = time.time() - start_time
        logger.info(f"Script generated in {script_time:.2f} seconds")

        # Save script
        script_path = os.path.join(self.output_dir, f"script_{index + 1}.txt")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
        logger.info(f"Script saved to: {script_path}")

        # Generate audio
        logger.info("Generating audio...")
        audio_path = os.path.join(self.audio_dir, f"audio_{index + 1}.mp3")
        start_time = time.time()

        # Check if ElevenLabs API key is available
        if not os.getenv("ELEVENLABS_API_KEY"):
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
            logger.info("Skipping audio generation - please set your API key")
            return True

        success = text_to_speech(script, output_path=audio_path)
        audio_time = time.time() - start_time

        if success:
            logger.info(f"Audio generated in {audio_time:.2f} seconds")
            logger.info(f"Audio saved to: {audio_path}")
        else:
            logger.error("Audio generation failed")

        return True

    def play_audio(self, index):
        """Play the audio for a specific article"""
        audio_path = os.path.join(self.audio_dir, f"audio_{index + 1}.mp3")
        if os.path.exists(audio_path):
            logger.info(f"Playing audio for article {index + 1}")
            try:
                # Stop any currently playing audio
                pygame.mixer.music.stop()

                # Load and play the new audio
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()

                # Wait for the audio to finish playing
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

                return True
            except Exception as e:
                logger.error(f"Error playing audio: {str(e)}")
                return False
        else:
            logger.error(f"Audio file not found: {audio_path}")
            return False

    def process_next_article(self):
        """Process the next article in the queue"""
        logger.info("\n" + "="*50)
        logger.info(f"Processing next article (index: {self.current_article_index})")
        logger.info("="*50)

        if self._process_article(self.current_article_index):
            self.current_article_index += 1
            logger.info(f"Successfully processed article. Next article index: {self.current_article_index}")
            return True

        logger.info("No more articles to process")
        return False

    def get_remaining_articles(self):
        """Get information about remaining articles"""
        remaining = len(self.ranked_articles) - self.current_article_index
        if remaining > 0:
            logger.info(f"\nRemaining articles: {remaining}")
            logger.info("Next articles in queue:")
            for i in range(self.current_article_index, min(self.current_article_index + 3, len(self.ranked_articles))):
                article = self.ranked_articles[i]
                logger.info(f"{i + 1}. Score: {article.score:.2f} - {article.title[:100]}...")
        else:
            logger.info("\nNo more articles to process")
        return remaining

def print_help():
    """Print available commands"""
    print("\nAvailable commands:")
    print("  next    - Process next article")
    print("  list    - Show remaining articles")
    print("  help    - Show this help message")
    print("  exit    - Exit the program")
    print("  status  - Show current status")
    print("  play    - Play the last generated audio")
    print("  play N  - Play audio for article N (e.g., 'play 1' for first article)")
    print("  stop    - Stop current audio playback")

def main():
    try:
        logger.info("\n" + "="*50)
        logger.info("Starting News Pipeline")
        logger.info("="*50)

        # Check for ElevenLabs API key
        if not os.getenv("ELEVENLABS_API_KEY"):
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
            logger.warning("Audio generation will be skipped")
            print("\n⚠️  WARNING: ElevenLabs API key not found!")
            print("Set ELEVENLABS_API_KEY environment variable to enable audio generation")
            print("The pipeline will continue but skip audio generation steps.\n")

        # Initialize pipeline
        pipeline = NewsPipeline()

        # Step 1: Scrape articles
        pipeline.scrape_articles()

        # Step 2: Prioritize articles
        pipeline.prioritize_articles()

        # Step 3: Generate initial content
        pipeline.generate_initial_content()

        logger.info("\n" + "="*50)
        logger.info("Initial pipeline setup completed")
        logger.info("Entering interactive mode")
        logger.info("="*50)

        print_help()

        while True:
            try:
                command = input("\nEnter command (or 'help' for options): ").strip().lower()

                if command == 'exit':
                    logger.info("Exiting program")
                    break
                elif command == 'next':
                    if not pipeline.process_next_article():
                        logger.info("No more articles to process")
                elif command == 'list':
                    pipeline.get_remaining_articles()
                elif command == 'help':
                    print_help()
                elif command == 'status':
                    logger.info(f"Current article index: {pipeline.current_article_index}")
                    logger.info(f"Total articles: {len(pipeline.ranked_articles)}")
                    pipeline.get_remaining_articles()
                elif command == 'play':
                    # Play the last generated audio
                    pipeline.play_audio(pipeline.current_article_index - 1)
                elif command == 'stop':
                    pygame.mixer.music.stop()
                    logger.info("Audio playback stopped")
                elif command.startswith('play '):
                    try:
                        # Extract article number from command
                        article_num = int(command.split()[1]) - 1
                        if 0 <= article_num < pipeline.current_article_index:
                            pipeline.play_audio(article_num)
                        else:
                            logger.error(f"Invalid article number. Must be between 1 and {pipeline.current_article_index}")
                    except ValueError:
                        logger.error("Invalid article number. Use 'play N' where N is the article number")
                else:
                    logger.info("Unknown command. Type 'help' for available commands.")

            except KeyboardInterrupt:
                logger.info("\nReceived keyboard interrupt. Type 'exit' to quit.")
            except Exception as e:
                logger.error(f"Error processing command: {str(e)}")

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise
    finally:
        # Clean up pygame
        pygame.mixer.quit()

if __name__ == "__main__":
    main()