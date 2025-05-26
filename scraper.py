import os
import logging
import time
from typing import List, Dict, Optional, Set
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler
import glob

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
    def __init__(self, username: str, uni_id: str, password: str):
        self.username = username
        self.uni_id = uni_id
        self.password = password
        self.driver = None
        self.wait = None
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
        
        # Initialize or restore session
        self.initialize_or_restore_session()

    def initialize_or_restore_session(self) -> bool:
        """Initialize a new session or restore an existing one."""
        try:
            # First try to restore existing session
            if self.load_session():
                logger.info("Successfully restored existing session")
                return True
                
            # If no valid session exists, create a new one
            logger.info("No valid session found, creating new session...")
            self.setup_driver()
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

    def quick_homepage_update(self) -> List[Dict]:
        """Perform a quick scrape of the FT homepage for breaking news."""
        try:
            logger.info("Performing quick homepage update...")
            self.setup_driver()
            
            if not self.login():
                logger.error("Failed to login for quick update")
                return []

            # Only scrape the homepage
            self.driver.get("https://www.ft.com/")
            time.sleep(2)

            # Extract only the top stories
            previews = self._extract_previews_from_page()
            
            # Filter for only very recent articles (last hour)
            recent_previews = []
            for preview in previews:
                try:
                    # Try to get article timestamp from the page
                    article_url = preview['url']
                    self.driver.get(article_url)
                    time.sleep(1)
                    
                    try:
                        date_element = self.driver.find_element(By.CSS_SELECTOR, "time")
                        article_time = datetime.fromisoformat(date_element.get_attribute("datetime"))
                        if (datetime.now() - article_time).total_seconds() <= 3600:  # Last hour
                            recent_previews.append(preview)
                    except:
                        # If we can't get the time, include the article
                        recent_previews.append(preview)
                except:
                    continue

            logger.info(f"Found {len(recent_previews)} recent articles from homepage")
            return recent_previews

        except Exception as e:
            logger.error(f"Quick homepage update failed: {str(e)}")
            return []
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def setup_driver(self) -> None:
        """Initialize the Chrome WebDriver with appropriate options."""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # First, ensure no existing ChromeDriver processes are running
                try:
                    if os.name == 'nt':  # Windows
                        os.system('taskkill /f /im chromedriver.exe')
                    else:  # Unix/Linux/Mac
                        os.system('pkill chromedriver')
                except Exception as e:
                    logger.warning(f"Failed to kill existing ChromeDriver processes: {str(e)}")

                chrome_options = Options()
                chrome_options.add_argument('--headless=new')  # Enable headless mode
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
                
                # Add performance optimizations
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-infobars')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                
                # Add additional stability options
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--allow-running-insecure-content')
                chrome_options.add_argument('--ignore-certificate-errors')
                
                # Configure ChromeDriver service with specific port
                service = Service(
                    ChromeDriverManager().install(),
                    port=0  # Let the system assign an available port
                )
                
                logger.info("Starting Chrome WebDriver in headless mode...")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
                # Set up wait with explicit timeout
                self.wait = WebDriverWait(self.driver, 20)
                
                # Test the connection with a simple page load
                logger.info("Testing WebDriver connection...")
                self.driver.get("about:blank")
                
                # Verify we can interact with the browser
                self.driver.execute_script("return navigator.userAgent")
                
                logger.info("Chrome WebDriver initialized successfully")
                return
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed to initialize WebDriver: {str(e)}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise Exception("Failed to initialize Chrome WebDriver after multiple attempts")

    def save_session(self) -> None:
        """Save current session cookies and visited URLs."""
        if self.driver:
            try:
                cookies = self.driver.get_cookies()
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
                
            # Initialize driver if not already done
            if not self.driver:
                self.setup_driver()
                
            # Load cookies
            if self.driver:
                for cookie in session_data['cookies']:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Failed to load cookie: {str(e)}")
                        
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
        if not self.driver:
            return False
            
        try:
            # Check for myFT link which indicates we're logged in
            myft_link = self.driver.find_element(By.CSS_SELECTOR, "a[href='/myft']")
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

            # Ensure driver is initialized
            if not self.driver:
                logger.info("Initializing WebDriver for login...")
                self.setup_driver()
                if not self.driver:
                    logger.error("Failed to initialize WebDriver")
                    return False

            # Check if we're already on a logged-in page
            try:
                myft_link = self.driver.find_element(By.CSS_SELECTOR, "a[href='/myft']")
                logger.info("Already logged in (found myFT link)")
                self.is_logged_in = True
                return True
            except NoSuchElementException:
                pass  # Not logged in, continue with login process

            logger.info("Navigating to FT login page...")
            self.driver.get("https://www.ft.com/login")
            
            # Wait for page to be fully loaded
            try:
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                time.sleep(2)  # Additional wait for dynamic content
            except Exception as e:
                logger.error(f"Failed to load login page: {str(e)}")
                return False

            # Enter email
            try:
                username_field = self.wait.until(EC.presence_of_element_located((By.ID, "enter-email")))
                username_field.clear()  # Clear any existing text
                username_field.send_keys(self.username)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to enter username: {str(e)}")
                return False

            # Click Next button
            try:
                next_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]")))
                next_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to click Next button: {str(e)}")
                return False

            # Click SSO sign in
            try:
                sso_button = self.wait.until(EC.element_to_be_clickable((By.ID, "sso-redirect-button")))
                sso_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to click SSO button: {str(e)}")
                return False

            # University login
            try:
                # Wait for the university login page to load
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                time.sleep(2)

                # Find and fill username field
                username_field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']")))
                username_field.clear()
                username_field.send_keys(self.uni_id)
                time.sleep(0.5)

                # Find and fill password field
                password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                password_field.clear()
                password_field.send_keys(self.password)
                time.sleep(0.5)

                # Find and click login button
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed during university login: {str(e)}")
                return False

            # Verify login success
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/myft']")))
                self.is_logged_in = True
                self.save_session()
                logger.info("Login successful")
                return True
            except Exception as e:
                logger.error(f"Failed to verify login success: {str(e)}")
                # Take a screenshot of the error
                try:
                    screenshot_path = os.path.join(self.data_dir, "login_error.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved login error screenshot to {screenshot_path}")
                except:
                    pass
                return False

        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            # Take a screenshot of the error
            try:
                screenshot_path = os.path.join(self.data_dir, "login_error.png")
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Saved login error screenshot to {screenshot_path}")
            except:
                pass
            return False

    def scrape_articles(self) -> List[Dict]:
        """Main method to scrape articles with prioritization."""
        scraping_errors = []  # List to collect errors
        
        try:
            logger.info("Setting up Chrome WebDriver...")
            self.setup_driver()

            # First, try to login only once
            logger.info("Attempting to login...")
            if not self.login():
                logger.error("Failed to login")
                return []

            # Wait a moment after login
            time.sleep(3)
            logger.info("Login successful")

            # First, try to load existing previews
            previews_file = os.path.join(self.data_dir, "article_previews.json")
            if os.path.exists(previews_file):
                try:
                    with open(previews_file, 'r', encoding='utf-8') as f:
                        existing_previews = json.load(f)
                    logger.info(f"Found {len(existing_previews)} existing article previews")
                    
                    # Check if we need to update previews (e.g., if they're too old)
                    if self._should_update_previews(existing_previews):
                        logger.info("Existing previews are too old, updating...")
                        # Reset visited URLs to force a fresh scrape
                        self.visited_urls = set()
                        self.seen_preview_urls = set()
                        self.save_progress()
                        new_previews = self.get_article_previews()
                        # Merge new previews with existing ones, avoiding duplicates
                        all_previews = self._merge_previews(existing_previews, new_previews)
                    else:
                        logger.info("Using existing previews")
                        all_previews = existing_previews
                except Exception as e:
                    logger.error(f"Failed to load existing previews: {str(e)}")
                    scraping_errors.append(f"Failed to load existing previews: {str(e)}")
                    # Reset visited URLs and try fresh scrape
                    self.visited_urls = set()
                    self.seen_preview_urls = set()
                    self.save_progress()
                    all_previews = self.get_article_previews()
            else:
                logger.info("No existing previews found, collecting new ones...")
                # Ensure visited URLs is empty for fresh scrape
                self.visited_urls = set()
                self.seen_preview_urls = set()
                self.save_progress()
                all_previews = self.get_article_previews()

            # Even if no new previews were found, return existing ones
            if not all_previews:
                logger.warning("No new article previews were found")
                if os.path.exists(previews_file):
                    try:
                        with open(previews_file, 'r', encoding='utf-8') as f:
                            existing_previews = json.load(f)
                        logger.info(f"Using {len(existing_previews)} existing previews")
                        return existing_previews
                    except Exception as e:
                        logger.error(f"Failed to load existing previews: {str(e)}")
                return []

            # Save the final previews
            try:
                with open(previews_file, 'w', encoding='utf-8') as f:
                    json.dump(all_previews, f, indent=2)
                logger.info(f"Saved {len(all_previews)} article previews to {previews_file}")
            except Exception as e:
                error_msg = f"Failed to save previews to file: {str(e)}"
                logger.error(error_msg)
                scraping_errors.append(error_msg)

            # Save individual article files for prioritization
            output_dir = "scraped_articles"
            os.makedirs(output_dir, exist_ok=True)
            
            successful_saves = 0
            for i, preview in enumerate(all_previews, 1):
                try:
                    safe_title = self._sanitize_filename(preview['headline'])
                    article_file = os.path.join(output_dir, f"article_{i}_{safe_title}.txt")
                    with open(article_file, 'w', encoding='utf-8') as f:
                        f.write(f"Title: {preview['headline']}\n")
                        f.write(f"URL: {preview['url']}\n")
                        if preview.get('standfirst'):
                            f.write(f"Summary: {preview['standfirst']}\n")
                        f.write("\n" + "="*50 + "\n\n")
                        # Add placeholder for full text that will be scraped later
                        f.write("Full text will be scraped during prioritization phase.\n")
                    successful_saves += 1
                except Exception as e:
                    error_msg = f"Failed to save article {i} ({preview['headline']}): {str(e)}"
                    logger.error(error_msg)
                    scraping_errors.append(error_msg)
                    continue
            
            logger.info(f"Successfully saved {successful_saves} out of {len(all_previews)} article files to {output_dir}")

            # Report any errors that occurred during scraping
            if scraping_errors:
                logger.warning("\n" + "="*50)
                logger.warning("The following errors occurred during scraping:")
                for error in scraping_errors:
                    logger.warning(f"- {error}")
                logger.warning("="*50 + "\n")
                logger.warning(f"Scraping completed with {len(scraping_errors)} errors")
            else:
                logger.info("Scraping completed successfully with no errors")

            # Save the last scrape time after successful completion
            self.save_last_scrape_time()
            return all_previews

        except Exception as e:
            error_msg = f"Critical scraping error: {str(e)}"
            logger.error(error_msg)
            scraping_errors.append(error_msg)
            # Try to return existing previews if available
            if os.path.exists(previews_file):
                try:
                    with open(previews_file, 'r', encoding='utf-8') as f:
                        existing_previews = json.load(f)
                    logger.info(f"Returning {len(existing_previews)} existing previews after error")
                    return existing_previews
                except Exception as e:
                    logger.error(f"Failed to load existing previews after error: {str(e)}")
            return []
        finally:
            # Report any errors that occurred during scraping
            if scraping_errors:
                logger.warning("\n" + "="*50)
                logger.warning("The following errors occurred during scraping:")
                for error in scraping_errors:
                    logger.warning(f"- {error}")
                logger.warning("="*50 + "\n")
                logger.warning(f"Scraping completed with {len(scraping_errors)} errors")

    def _should_update_previews(self, previews: List[Dict]) -> bool:
        """Check if previews need to be updated based on age."""
        if not previews:
            return True
            
        # Get the timestamp from the first preview (assuming they're all from the same scraping session)
        try:
            timestamp = datetime.fromisoformat(previews[0].get('timestamp', ''))
            # Update if previews are older than 1 hour
            return (datetime.now() - timestamp).total_seconds() > 3600
        except:
            return True

    def _merge_previews(self, existing: List[Dict], new: List[Dict]) -> List[Dict]:
        """Merge new previews with existing ones, avoiding duplicates."""
        seen_urls = {p['url'] for p in existing}
        merged = existing.copy()
        
        for preview in new:
            if preview['url'] not in seen_urls:
                merged.append(preview)
                seen_urls.add(preview['url'])
                
        return merged

    def get_article_previews(self) -> List[Dict]:
        """Get article previews from multiple source pages"""
        logger.info("Getting article previews from multiple sources...")
        all_previews = []

        # Define source pages
        source_pages = [
            "https://www.ft.com/myft/following/a32973f6-1343-424d-9e65-8b3cceb04743",
            "https://www.ft.com/markets?page=1",
            "https://www.ft.com/technology",
            "https://www.ft.com/opinion",
            "https://www.ft.com/world"
        ]

        for source_url in source_pages:
            try:
                logger.info(f"Processing source page: {source_url}")
                self.driver.get(source_url)
                
                # Wait for page to load and content to be visible
                try:
                    # First wait for the page to be fully loaded
                    self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                    time.sleep(3)  # Additional wait for dynamic content
                    
                    # Check if this is a myFT following page first
                    if "myft/following" in source_url:
                        logger.info("Detected myFT following page, skipping article teaser checks")
                    else:
                        # Try multiple selectors with a shorter timeout
                        selectors = [
                            "div.o-teaser",
                            "div.o-teaser--hero",
                            "div.o-teaser--top-stories",
                            "article.o-teaser",
                            "div.o-teaser__content",
                            "div.o-teaser__heading"
                        ]
                        
                        element_found = False
                        for selector in selectors:
                            try:
                                WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                                element_found = True
                                logger.info(f"Found content with selector: {selector}")
                                break
                            except TimeoutException:
                                continue
                        
                        if not element_found:
                            logger.warning("No article elements found with any selector")
                            # Take a screenshot for debugging
                            screenshot_path = os.path.join(self.data_dir, f"no_content_{source_url.replace('https://', '').replace('/', '_')}.png")
                            self.driver.save_screenshot(screenshot_path)
                            logger.info(f"Saved no-content screenshot to {screenshot_path}")
                            continue
                        
                except TimeoutException:
                    logger.warning("Timeout waiting for page content")
                    # Take a screenshot for debugging
                    screenshot_path = os.path.join(self.data_dir, f"timeout_{source_url.replace('https://', '').replace('/', '_')}.png")
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"Saved timeout screenshot to {screenshot_path}")
                    continue

                # Scroll to load more content
                logger.info("Scrolling to load more content...")
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0
                max_scroll_attempts = 10  # Maximum number of scroll attempts
                no_change_count = 0  # Counter for consecutive no-change scrolls
                
                while scroll_attempts < max_scroll_attempts:
                    # Scroll down
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)  # Wait for content to load
                    
                    # Calculate new scroll height
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        no_change_count += 1
                        if no_change_count >= 3:  # If height hasn't changed for 3 consecutive attempts
                            logger.info("No new content loaded after multiple attempts, stopping scroll")
                            break
                    else:
                        no_change_count = 0  # Reset counter if height changed
                        
                    last_height = new_height
                    scroll_attempts += 1
                    logger.info(f"Scrolled down, new content loaded (attempt {scroll_attempts}/{max_scroll_attempts})")
                
                if scroll_attempts >= max_scroll_attempts:
                    logger.info("Reached maximum scroll attempts, moving to next page")

                # Special handling for World section
                if "world" in source_url:
                    # Get all sub-navigation links
                    subnav_links = self.driver.find_elements(By.CSS_SELECTOR, "a.o-header__subnav-link")
                    subnav_urls = []
                    
                    for link in subnav_links:
                        try:
                            href = link.get_attribute('href')
                            if href:
                                subnav_urls.append(href)
                                logger.debug(f"Found subnav link: {href}")
                        except Exception as e:
                            logger.warning(f"Failed to get subnav link: {str(e)}")
                            continue

                    # Process each sub-navigation page
                    for subnav_url in subnav_urls:
                        try:
                            logger.info(f"Processing subnav page: {subnav_url}")
                            self.driver.get(subnav_url)
                            
                            # Wait for content to load
                            try:
                                WebDriverWait(self.driver, 10).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.o-teaser, div.o-teaser--hero, div.o-teaser--top-stories"))
                                )
                            except TimeoutException:
                                logger.warning(f"Timeout waiting for subnav page content: {subnav_url}")
                                continue
                            
                            # Scroll to load more content
                            last_height = self.driver.execute_script("return document.body.scrollHeight")
                            while True:
                                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                time.sleep(2)
                                new_height = self.driver.execute_script("return document.body.scrollHeight")
                                if new_height == last_height:
                                    break
                                last_height = new_height
                            
                            # Extract previews from subnav page
                            subnav_previews = self._extract_previews_from_page()
                            if subnav_previews:
                                # Add timestamp to each preview
                                for preview in subnav_previews:
                                    preview['timestamp'] = datetime.now().isoformat()
                                all_previews.extend(subnav_previews)
                                logger.info(f"Found {len(subnav_previews)} previews on subnav page")
                            
                        except Exception as e:
                            logger.error(f"Failed to process subnav page {subnav_url}: {str(e)}")
                            continue

                # Extract previews from main source page
                page_previews = self._extract_previews_from_page()
                if page_previews:
                    # Add timestamp to each preview
                    for preview in page_previews:
                        preview['timestamp'] = datetime.now().isoformat()
                    all_previews.extend(page_previews)
                    logger.info(f"Found {len(page_previews)} previews on main page")

            except Exception as e:
                logger.error(f"Failed to process source page {source_url}: {str(e)}")
                continue

        # Remove duplicates based on URL
        unique_previews = []
        seen_urls = set()
        for preview in all_previews:
            if preview['url'] not in seen_urls:
                unique_previews.append(preview)
                seen_urls.add(preview['url'])

        logger.info(f"Found {len(unique_previews)} unique article previews")
        return unique_previews

    def _extract_previews_from_page(self) -> List[Dict]:
        """Extract article previews from the current page"""
        previews = []
        try:
            # Log the current URL for debugging
            current_url = self.driver.current_url
            logger.info(f"Extracting previews from: {current_url}")
            
            # Check if this is a myFT following page
            if "myft/following" in current_url:
                logger.info("Detected myFT following page, looking for o3-type-body-base spans")
                
                # Wait for the spans to load
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.o3-type-body-base")))
                
                # Find all spans with the specific class
                content_spans = self.driver.find_elements(By.CSS_SELECTOR, "span.o3-type-body-base")
                logger.info(f"Found {len(content_spans)} content spans")
                
                for span in content_spans:
                    try:
                        content = span.text.strip()
                        if not content:
                            continue
                            
                        # Find the associated link using the specific class for myFT pages
                        link = span.find_element(By.XPATH, "ancestor::div[contains(@class, 'topic-card')]//a[contains(@class, 'topic-card__concept-article-link')]")
                        url = link.get_attribute('href')
                        
                        # Check if we've seen this URL before in previews
                        if url in self.seen_preview_urls:
                            logger.info(f"Found previously seen article in previews, stopping page processing")
                            return previews
                        
                        if url and content:
                            preview = {
                                'headline': content,
                                'url': url,
                                'timestamp': datetime.now().isoformat()
                            }
                            previews.append(preview)
                            self.seen_preview_urls.add(url)  # Add to seen previews
                            logger.debug(f"Added myFT preview: {content[:50]}...")
                    except Exception as e:
                        logger.debug(f"Failed to extract myFT preview from span: {str(e)}")
                        continue
            else:
                # Original article extraction logic for regular pages
                # Try to find any clickable elements that might be articles
                clickable_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/content/'], a[href*='/articles/']")
                logger.info(f"Found {len(clickable_elements)} potential article links")
                
                for element in clickable_elements:
                    try:
                        url = element.get_attribute('href')
                        if not url or not url.startswith('https://www.ft.com/'):
                            continue
                            
                        # Check if we've seen this URL before in previews
                        if url in self.seen_preview_urls:
                            logger.info(f"Found previously seen article in previews, stopping page processing")
                            return previews
                            
                        # Try different ways to get the headline
                        headline = None
                        try:
                            headline = element.text.strip()
                        except:
                            try:
                                parent = element.find_element(By.XPATH, "./..")
                                headline = parent.text.strip()
                            except:
                                continue
                        
                        if not headline:
                            continue
                            
                        # Add the preview
                        preview = {
                            'headline': headline,
                            'url': url,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        previews.append(preview)
                        self.seen_preview_urls.add(url)  # Add to seen previews
                        logger.debug(f"Added preview: {headline[:50]}...")
                        
                    except Exception as e:
                        logger.debug(f"Failed to extract article preview from element: {str(e)}")
                        continue

            # If no previews found, save the page HTML for debugging
            if not previews:
                html_path = os.path.join(self.data_dir, f"page_{current_url.replace('https://', '').replace('/', '_')}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                logger.info(f"Saved page HTML to {html_path}")

        except Exception as e:
            logger.error(f"Failed to extract previews from page: {str(e)}")

        logger.info(f"Successfully extracted {len(previews)} previews from page")
        return previews

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename by removing invalid characters."""
        # Remove invalid characters for Windows filenames
        invalid_chars = '<>:"/\\|?*'
        # Replace invalid characters with underscore
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove any leading/trailing spaces and dots
        filename = filename.strip('. ')
        
        # Replace multiple consecutive underscores with a single one
        while '__' in filename:
            filename = filename.replace('__', '_')
            
        # Ensure the filename isn't empty after sanitization
        if not filename:
            filename = 'untitled_article'
            
        # Limit filename length to avoid path too long errors
        if len(filename) > 100:
            filename = filename[:100]
            
        return filename

    def scrape_full_article(self, url, is_initial_scrape=False):
        """Scrape a full article from its URL"""
        try:
            logger.info(f"Scraping full article: {url}")
            
            # Navigate to the article URL
            self.driver.get(url)
            
            # Wait for page to load completely
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            # Check for paywall indicators
            paywall_selectors = [
                '.o-topper__paywall',
                '.o-topper__premium',
                '.o-topper__locked',
                '.o-topper__content--premium',
                '.o-topper__content--locked'
            ]
            
            for selector in paywall_selectors:
                try:
                    if self.driver.find_element(By.CSS_SELECTOR, selector):
                        logger.warning(f"Article is behind paywall (detected {selector})")
                        return None
                except NoSuchElementException:
                    continue
            
            # Extract article metadata
            article_data = {
                'url': url,
                'title': None,
                'date': None,
                'author': None,
                'full_text': None
            }
            
            # Try multiple selectors for title
            title_selectors = [
                'h1.o-topper__headline',
                'h1[data-trackable="headline"]',
                'h1.o-topper__headline--large',
                'h1',
                '.o-topper__headline'
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if title_elem and title_elem.text.strip():
                        article_data['title'] = title_elem.text.strip()
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if not article_data['title']:
                logger.error("Could not find article title")
                return None
            
            # Try to get date
            date_selectors = [
                'time.o-topper__timestamp',
                'time[datetime]',
                '.o-topper__timestamp',
                'time'
            ]
            
            for selector in date_selectors:
                try:
                    date_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    article_data['date'] = date_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
            if not article_data['date']:
                logger.warning("Could not find article date")
            
            # Try to get author
            author_selectors = [
                '.o-topper__byline',
                '.o-topper__author',
                '.o-topper__byline-name',
                '.o-topper__author-name'
            ]
            
            for selector in author_selectors:
                try:
                    author_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    article_data['author'] = author_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
            if not article_data['author']:
                logger.warning("Could not find article author")
            
            # Try multiple selectors for article content
            content_selectors = [
                'article#article-body.n-content-body',  # Opinion article body
                'div.o-body',
                'div[data-trackable="article-body"]',
                'article.o-topper',
                'div.o-topper__content-wrapper',
                'div.o-topper__content',
                'div.o-topper__standfirst',
                'div.o-article-body',
                'div.o-article__body',
                'div.article__body',
                'div.article-body',
                'div[class*="article-body"]',
                'div[class*="article__body"]',
                'div[class*="o-body"]',
            ]
            
            article_text = []
            content_found = False
            
            for selector in content_selectors:
                try:
                    # Wait for content to be present
                    content_elem = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    # Get all text content
                    text = content_elem.text.strip()
                    if text:
                        article_text.append(text)
                        logger.info(f"Found content with selector: {selector}")
                        content_found = True
                        break  # Stop after finding content with first successful selector
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if not content_found:
                # If no content found with selectors, try getting all text from the page
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, 'body').text
                    if body_text:
                        article_text.append(body_text)
                        logger.info("Falling back to body text")
                        content_found = True
                except:
                    pass
            
            if not content_found:
                logger.error("Could not find article content")
                return None
            
            # Combine all found text
            article_data['full_text'] = '\n\n'.join(article_text)
            
            # Save article data to file
            safe_title = "".join(c for c in article_data['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50]  # Limit length
            filename = os.path.join(self.data_dir, f"article_{safe_title}.txt")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Title: {article_data['title']}\n")
                f.write(f"URL: {url}\n")
                if article_data['date']:
                    f.write(f"Date: {article_data['date']}\n")
                if article_data['author']:
                    f.write(f"Author: {article_data['author']}\n")
                f.write("\n" + "="*50 + "\n\n")
                f.write(article_data['full_text'])
            
            logger.info(f"Successfully scraped and saved article: {article_data['title']}")
            return article_data
            
        except Exception as e:
            logger.error(f"Error scraping article: {str(e)}")
            return None

    def cleanup(self):
        """Clean up resources but keep the session alive."""
        if self.driver:
            self.save_session()
            # Don't quit the driver, just minimize the window
            try:
                self.driver.minimize_window()
            except:
                pass

    def force_cleanup(self):
        """Force cleanup of all resources including the browser."""
        if self.driver:
            self.save_session()
            self.driver.quit()
            self.driver = None

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

