import os
import logging
import time
from typing import List, Dict, Optional, Set
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler
import glob
import sys
import asyncio
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import random

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging with rotation
def setup_logging():
    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Create rotating file handler
    log_file = os.path.join(LOGS_DIR, "scraper.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,  # Keep 5 backup files
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Clean up old pipeline logs
    cleanup_old_logs()

def cleanup_old_logs():
    """Clean up old pipeline logs, keeping only the last 5."""
    try:
        # Get all pipeline log files
        pipeline_logs = glob.glob(os.path.join(LOGS_DIR, "pipeline_*.log"))
        
        # Sort by modification time (newest first)
        pipeline_logs.sort(key=os.path.getmtime, reverse=True)
        
        # Remove old logs, keeping only the last 5
        for old_log in pipeline_logs[5:]:
            try:
                os.remove(old_log)
                logging.info(f"Removed old log file: {old_log}")
            except Exception as e:
                logging.error(f"Failed to remove old log file {old_log}: {str(e)}")
    except Exception as e:
        logging.error(f"Error during log cleanup: {str(e)}")

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load environment variables from .env file
logger.debug("Loading .env file...")
load_dotenv()
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"FT_USERNAME from env: {os.getenv('FT_USERNAME')}")
logger.debug(f"FT_PASSWORD from env: {os.getenv('FT_PASSWORD')}")

class FTScraper:
    def __init__(self, username: str = None, uni_id: str = None, password: str = None):
        self.driver = None
        self.visited_urls: Set[str] = set()
        self.seen_preview_urls: Set[str] = set()
        self.article_previews: List[Dict] = []
        
        # Create data directory if it doesn't exist
        self.data_dir = "scraped_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load existing progress
        self.progress_file = os.path.join(self.data_dir, "scraping_progress.json")
        self.load_progress()

    async def initialize(self):
        """Initialize the scraper."""
        try:
            # Run Selenium initialization in a thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, self._sync_init)
                return True
        except Exception as e:
            print(f"Selenium initialization failed: {str(e)}")
            raise

    def _sync_init(self):
        try:
            # Set up Chrome options
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--headless')  # Run in headless mode
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--remote-debugging-port=9222')  # Add debugging port
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Use local ChromeDriver with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    service = Service(executable_path="./chromedriver.exe")
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.set_page_load_timeout(30)  # Set page load timeout
                    print("Selenium WebDriver initialized successfully")
                    return
                except Exception as e:
                    print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retrying
                    else:
                        raise
        except Exception as e:
            print(f"Failed to initialize ChromeDriver: {str(e)}")
            raise

    def load_progress(self) -> None:
        """Load existing scraping progress."""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    self.visited_urls = set(progress_data.get('visited_urls', []))
                    self.seen_preview_urls = set(progress_data.get('seen_preview_urls', []))
                    print(f"Loaded {len(self.visited_urls)} previously visited URLs")
        except Exception as e:
            print(f"Failed to load progress: {str(e)}")
            self.visited_urls = set()
            self.seen_preview_urls = set()

    def _save_visited_urls(self) -> None:
        """Save current scraping progress."""
        try:
            progress_data = {
                'visited_urls': list(self.visited_urls),
                'seen_preview_urls': list(self.seen_preview_urls),
                'timestamp': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
            print(f"Saved progress: {len(self.visited_urls)} visited URLs")
        except Exception as e:
            print(f"Failed to save progress: {str(e)}")

    def cleanup(self):
        """Clean up resources."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                print("ChromeDriver cleaned up successfully")
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            # Force cleanup if normal cleanup fails
            self.force_cleanup()

    def force_cleanup(self):
        """Force cleanup of all resources."""
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            print("ChromeDriver force cleaned up")
        except Exception as e:
            print(f"Error during force cleanup: {str(e)}")

def main():
    # Get credentials from .env file
    username = os.getenv("FT_USERNAME")
    uni_id = os.getenv("FT_UNI_ID")
    password = os.getenv("FT_PASSWORD")
    
    if not all([username, uni_id, password]):
        logger.error("Missing FT credentials in environment variables")
        return

    scraper = FTScraper(username, uni_id, password)
    try:
        logger.info("Starting article scraping process...")
        previews = scraper.scrape_articles()

        if not previews:
            logger.error("No article previews were found")
            return

        logger.info(f"Successfully scraped {len(previews)} article previews")
        logger.info("Article previews saved to article_previews.json")
    finally:
        # Clean up resources
        scraper.force_cleanup()

if __name__ == "__main__":
    main()

