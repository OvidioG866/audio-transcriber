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
    async def initialize(self):
        """Initialize Playwright and browser."""
        try:
            # Log system information
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Python version: {sys.version}")
            logger.info(f"Environment variables: {dict(os.environ)}")
            
            # Check if Playwright browsers are installed
            try:
                playwright = await async_playwright().start()
                browser_path = playwright.chromium.executable_path
                logger.info(f"Chromium browser path: {browser_path}")
                if not os.path.exists(browser_path):
                    raise Exception(f"Chromium browser not found at {browser_path}")
                await playwright.stop()
            except Exception as browser_check_error:
                logger.error(f"Browser check failed: {str(browser_check_error)}")
                raise Exception(f"Browser check failed: {str(browser_check_error)}")
            
            logger.info("Initializing Playwright...")
            try:
                self.playwright = await async_playwright().start()
                logger.info("Playwright started successfully")
            except Exception as playwright_error:
                logger.error(f"Failed to start Playwright: {str(playwright_error)}")
                logger.error(f"Error type: {type(playwright_error)}")
                logger.error(f"Error details: {playwright_error.__dict__}")
                raise Exception(f"Failed to start Playwright: {str(playwright_error)}")
            
            try:
                logger.info("Launching browser...")
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-background-timer-throttling',
                        '--disable-backgrounding-occluded-windows',
                        '--disable-renderer-backgrounding',
                        '--single-process',
                        '--no-zygote'  # Added for better container compatibility
                    ],
                    executable_path=os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH')
                )
                logger.info("Browser launched successfully")
                
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.7103.114 Safari/537.36'
                )
                logger.info("Browser context created successfully")
                
                self.page = await self.context.new_page()
                logger.info("New page created successfully")
                
                return True
            except Exception as browser_error:
                logger.error(f"Browser initialization failed: {str(browser_error)}")
                logger.error(f"Error type: {type(browser_error)}")
                logger.error(f"Error details: {browser_error.__dict__}")
                if self.playwright:
                    await self.playwright.stop()
                raise Exception(f"Browser initialization failed: {str(browser_error)}")
                
        except Exception as e:
            logger.error(f"Playwright initialization failed: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {e.__dict__}")
            raise Exception(f"Playwright initialization failed: {str(e)}")

    def __init__(self, username: str, uni_id: str, password: str):
        self.username = username
        self.uni_id = uni_id
        self.password = password
        self.playwright = None
        self.browser = None
        self.page = None
        self.session_file = "ft_session.json"
        self.visited_urls: Set[str] = set()
        self.seen_preview_urls: Set[str] = set()
        self.article_previews: List[Dict] = []
        self.is_logged_in = False
        self.last_session_refresh = None
        
        # Create data directory if it doesn't exist
        self.data_dir = "scraped_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load existing progress
        self.progress_file = os.path.join(self.data_dir, "scraping_progress.json")
        self.last_scrape_file = os.path.join(self.data_dir, "last_scrape_time.json")
        self.load_progress()
        self.load_last_scrape_time()

    def initialize_or_restore_session(self) -> bool:
        """Initialize a new session or restore an existing one."""
        try:
            # First try to restore existing session
            if self.load_session():
                logger.info("Successfully restored existing session")
                return True
                
            # If no valid session exists, create a new one
            logger.info("No valid session found, creating new session...")
            if self.login():
                self.save_session()
                self.last_session_refresh = datetime.now()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to initialize/restore session: {str(e)}")
            return False

    def refresh_session_if_needed(self) -> bool:
        """Check if session needs refresh and refresh if necessary."""
        if not self.last_session_refresh:
            return self.initialize_or_restore_session()
            
        # Refresh session if it's been more than 12 hours
        time_since_refresh = datetime.now() - self.last_session_refresh
        if time_since_refresh.total_seconds() > 43200:  # 12 hours
            logger.info("Session refresh needed, refreshing...")
            if self.login():
                self.save_session()
                self.last_session_refresh = datetime.now()
                return True
            return False
            
        return True

    def load_progress(self) -> None:
        """Load existing scraping progress."""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    self.visited_urls = set(progress_data.get('visited_urls', []))
                    self.seen_preview_urls = set(progress_data.get('seen_preview_urls', []))
                    logger.info(f"Loaded {len(self.visited_urls)} previously visited URLs")
                    logger.info(f"Loaded {len(self.seen_preview_urls)} previously seen preview URLs")
                    
                    # If we have visited URLs but no previews, reset visited URLs
                    previews_file = os.path.join(self.data_dir, "article_previews.json")
                    if not os.path.exists(previews_file) or os.path.getsize(previews_file) == 0:
                        logger.info("No previews found despite visited URLs, resetting progress")
                        self.visited_urls = set()
                        self.seen_preview_urls = set()
                        self.save_progress()
        except Exception as e:
            logger.error(f"Failed to load progress: {str(e)}")
            self.visited_urls = set()
            self.seen_preview_urls = set()

    def save_progress(self) -> None:
        """Save current scraping progress."""
        try:
            progress_data = {
                'visited_urls': list(self.visited_urls),
                'seen_preview_urls': list(self.seen_preview_urls),
                'timestamp': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
            logger.info(f"Saved progress: {len(self.visited_urls)} visited URLs, {len(self.seen_preview_urls)} seen preview URLs")
        except Exception as e:
            logger.error(f"Failed to save progress: {str(e)}")

    def load_last_scrape_time(self) -> None:
        """Load the timestamp of the last full scrape."""
        try:
            if os.path.exists(self.last_scrape_file):
                with open(self.last_scrape_file, 'r') as f:
                    data = json.load(f)
                    self.last_scrape_time = datetime.fromisoformat(data['timestamp'])
            else:
                self.last_scrape_time = datetime.min
        except Exception as e:
            logger.error(f"Failed to load last scrape time: {str(e)}")
            self.last_scrape_time = datetime.min

    def save_last_scrape_time(self) -> None:
        """Save the current time as the last scrape time."""
        try:
            data = {
                'timestamp': datetime.now().isoformat()
            }
            with open(self.last_scrape_file, 'w') as f:
                json.dump(data, f)
            self.last_scrape_time = datetime.now()
        except Exception as e:
            logger.error(f"Failed to save last scrape time: {str(e)}")

    def should_perform_full_scrape(self) -> bool:
        """Check if enough time has passed since the last full scrape."""
        time_since_last_scrape = datetime.now() - self.last_scrape_time
        return time_since_last_scrape.total_seconds() > 10800  # 3 hours in seconds

    def save_session(self) -> None:
        """Save current session cookies and visited URLs."""
        if self.page:
            try:
                cookies = self.page.context.cookies()
                session_data = {
                    'cookies': cookies,
                    'visited_urls': list(self.visited_urls),
                    'seen_preview_urls': list(self.seen_preview_urls),
                    'timestamp': datetime.now().isoformat(),
                    'last_refresh': self.last_session_refresh.isoformat() if self.last_session_refresh else None
                }
                with open(self.session_file, 'w') as f:
                    json.dump(session_data, f)
                logger.info("Session saved successfully")
            except Exception as e:
                logger.error(f"Failed to save session: {str(e)}")

    def load_session(self) -> bool:
        """Load previous session if it exists and is not expired."""
        try:
            if not os.path.exists(self.session_file):
                return False
                
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
                
            # Check if session is expired (24 hours)
            session_time = datetime.fromisoformat(session_data['timestamp'])
            if (datetime.now() - session_time).total_seconds() > 86400:
                logger.info("Session expired, will need to login again")
                return False
                
            # Load cookies
            if self.page:
                self.page.context.add_cookies(session_data['cookies'])
                self.visited_urls = set(session_data['visited_urls'])
                self.seen_preview_urls = set(session_data['seen_preview_urls'])
                self.last_session_refresh = datetime.fromisoformat(session_data['last_refresh']) if session_data.get('last_refresh') else None
                
                # Verify session is still valid
                if self.verify_login_status():
                    self.is_logged_in = True
                    logger.info("Session loaded and verified successfully")
                    return True
                else:
                    logger.info("Session loaded but not valid, will login again")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to load session: {str(e)}")
            return False

    def verify_login_status(self) -> bool:
        """Verify if we're still logged in by checking for login indicators."""
        if not self.page:
            return False
            
        try:
            # Check for myFT link which indicates we're logged in
            self.page.goto("https://www.ft.com/")
            myft_link = self.page.wait_for_selector("a[href='/myft']", timeout=5000)
            self.is_logged_in = True
            return True
        except:
            self.is_logged_in = False
            return False

    def login(self) -> bool:
        """Log in to FT account if session is not valid."""
        try:
            # First check if we're already logged in
            if self.is_logged_in:
                logger.info("Already logged in, skipping login process")
                return True

            logger.info("Navigating to FT login page...")
            self.page.goto("https://www.ft.com/login")
            
            # Wait for page to be fully loaded
            self.page.wait_for_load_state('networkidle')
            
            # Enter email
            try:
                username_field = self.page.wait_for_selector("#enter-email")
                username_field.fill(self.username)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to enter username: {str(e)}")
                return False

            # Click Next button
            try:
                next_button = self.page.wait_for_selector("button:has-text('Next')")
                next_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to click Next button: {str(e)}")
                return False

            # Click SSO sign in
            try:
                sso_button = self.page.wait_for_selector("#sso-redirect-button")
                sso_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to click SSO button: {str(e)}")
                return False

            # University login
            try:
                # Wait for the university login page to load
                self.page.wait_for_load_state('networkidle')
                time.sleep(2)

                # Find and fill username field
                username_field = self.page.wait_for_selector("input[type='text'], input[type='email']")
                username_field.fill(self.uni_id)
                time.sleep(0.5)

                # Find and fill password field
                password_field = self.page.wait_for_selector("input[type='password']")
                password_field.fill(self.password)
                time.sleep(0.5)

                # Find and click login button
                login_button = self.page.wait_for_selector("button[type='submit']")
                login_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed during university login: {str(e)}")
                return False

            # Verify login success
            try:
                self.page.wait_for_selector("a[href='/myft']", timeout=10000)
                self.is_logged_in = True
                self.save_session()
                logger.info("Login successful")
                return True
            except Exception as e:
                logger.error(f"Failed to verify login success: {str(e)}")
                # Take a screenshot of the error
                try:
                    screenshot_path = os.path.join(self.data_dir, "login_error.png")
                    self.page.screenshot(path=screenshot_path)
                    logger.info(f"Saved login error screenshot to {screenshot_path}")
                except:
                    pass
                return False

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            # Take a screenshot of the error
            try:
                screenshot_path = os.path.join(self.data_dir, "login_error.png")
                self.page.screenshot(path=screenshot_path)
                logger.info(f"Saved login error screenshot to {screenshot_path}")
            except:
                pass
            return False

    def cleanup(self):
        """Clean up resources but keep the session alive."""
        if self.page:
            self.save_session()
            # Don't close the browser, just minimize the window
            try:
                self.page.evaluate("window.minimize()")
            except:
                pass

    def force_cleanup(self):
        """Force cleanup of all resources including the browser."""
        if self.page:
            self.save_session()
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.page = None
        self.browser = None
        self.playwright = None

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

