import os
import logging
import time
from typing import List, Dict, Optional
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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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

    def setup_driver(self) -> None:
        """Initialize the Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        # Enable headless mode
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--enable-unsafe-swiftshader')  # Added for WebGL
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Performance optimizations
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--disable-site-isolation-trials')

        # Memory optimizations
        chrome_options.add_argument('--disable-application-cache')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-breakpad')
        chrome_options.add_argument('--disable-component-extensions-with-background-pages')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-domain-reliability')
        chrome_options.add_argument('--disable-features=AudioServiceOutOfProcess')
        chrome_options.add_argument('--disable-hang-monitor')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        chrome_options.add_argument('--disable-prompt-on-repost')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--force-color-profile=srgb')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--password-store=basic')
        chrome_options.add_argument('--use-mock-keychain')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--mute-audio')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)  # Reduced timeout to 10 seconds

    def login(self) -> bool:
        """Log in to FT account."""
        try:
            logger.info("Navigating to FT login page...")
            self.driver.get("https://www.ft.com/login")
            time.sleep(1)  # Reduced from 3

            # Step 1: Enter email
            logger.info("Looking for email input field...")
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "enter-email"))
            )
            logger.info("Found email input field, entering email...")
            username_field.send_keys(self.username)
            time.sleep(1)  # Reduced from 2

            # Step 2: Click Next button - try multiple selectors
            logger.info("Looking for Next button...")
            try:
                next_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]"))
                )
            except TimeoutException:
                try:
                    next_button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.o-buttons.o-buttons--primary"))
                    )
                except TimeoutException:
                    next_button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                    )

            logger.info("Found Next button, clicking...")
            try:
                next_button.click()
            except:
                self.driver.execute_script("arguments[0].click();", next_button)

            time.sleep(2)  # Reduced from 5

            # Step 3: Click SSO sign in
            logger.info("Looking for SSO sign in button...")
            sso_button = None
            selectors = [
                (By.ID, "sso-redirect-button"),
                (By.XPATH, "//a[normalize-space(text())='SSO Sign in']"),
                (By.XPATH, "//a[contains(., 'SSO Sign in')])"),
                (By.XPATH, "//a[contains(., 'SSO')])"),
                (By.CSS_SELECTOR, "a.o-buttons.o-buttons--primary"),
                (By.CSS_SELECTOR, "a[type='submit']"),
                (By.CSS_SELECTOR, "a.main-button"),
                (By.XPATH, "//button[normalize-space(text())='SSO Sign in']"),
                (By.XPATH, "//button[contains(., 'SSO Sign in')])"),
            ]
            for by, selector in selectors:
                try:
                    sso_button = self.wait.until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if sso_button:
                        break
                except Exception:
                    continue

            if not sso_button:
                logger.error("Could not find SSO button with any selector")
                return False

            try:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", sso_button)
                time.sleep(0.5)  # Reduced from 1
                sso_button.click()
            except Exception as e:
                try:
                    self.driver.execute_script("arguments[0].click();", sso_button)
                except Exception as e2:
                    logger.error(f"Failed to click SSO button: {str(e)} / {str(e2)}")
                    return False

            time.sleep(2)  # Reduced from 5

            # Step 4: University login
            logger.info("Looking for university login form...")
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']"))
            )
            username_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
            logger.info("Entering university account number...")
            username_field.clear()
            username_field.send_keys(self.uni_id)
            time.sleep(0.5)  # Reduced from 1
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            logger.info("Entering university password...")
            password_field.send_keys(self.password)
            time.sleep(0.5)  # Reduced from 1
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            logger.info("Clicking university login button...")
            login_button.click()
            time.sleep(2)  # Reduced from 5

            # Wait for successful login
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/myft']"))
                )
                logger.info("Successfully logged in")
                return True
            except TimeoutException:
                logger.error("Timeout waiting for successful login")
                return False

        except TimeoutException:
            logger.error("Login failed - timeout waiting for elements")
            return False
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def get_article_links(self) -> list:
        """Get links to articles from MyFT page."""
        try:
            logger.info("Navigating to MyFT page...")
            self.driver.get("https://www.ft.com/myft")
            logger.info("Waiting for article links to load...")

            # Log the current URL
            logger.info(f"Current URL: {self.driver.current_url}")

            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.js-teaser-heading-link, a[data-trackable='heading-link'], .o-teaser__heading a"))
                )
                logger.info("Found article link elements")
            except TimeoutException:
                logger.error("Timeout waiting for article links to load")
                return []

            # Get article links
            links = []
            seen = set()
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a.js-teaser-heading-link, a[data-trackable='heading-link'], .o-teaser__heading a")
            logger.info(f"Found {len(elements)} potential article links")

            for a in elements:
                href = a.get_attribute("href")
                if href and href.startswith("https://www.ft.com/") and href not in seen:
                    links.append(href)
                    seen.add(href)
                    logger.info(f"Added article link: {href}")

            logger.info(f"Found {len(links)} valid article links on MyFT page")
            return links
        except Exception as e:
            logger.error(f"Failed to get article links from MyFT page: {str(e)}")
            return []

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape content from a single article."""
        try:
            logger.info(f"Scraping article: {url}")
            self.driver.get(url)

            # Wait for article content to load
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                logger.info("Found article title")
            except TimeoutException:
                logger.error("Timeout waiting for article title")
                return None

            # Extract article data
            title = self.driver.find_element(By.TAG_NAME, "h1").text
            logger.info(f"Article title: {title}")

            # Try to get publication date
            try:
                date_element = self.driver.find_element(By.CSS_SELECTOR, "time")
                date = date_element.get_attribute("datetime")
                logger.info(f"Found publication date: {date}")
            except NoSuchElementException:
                date = None
                logger.warning("Could not find publication date")

            # Try to get author
            try:
                author = self.driver.find_element(By.CSS_SELECTOR, ".o-topper__author").text
                logger.info(f"Found author: {author}")
            except NoSuchElementException:
                author = None
                logger.warning("Could not find author")

            # Get article text - handle multiple paragraphs
            try:
                article_body = self.driver.find_element(By.CSS_SELECTOR, "article.n-content-body")
                # Get all paragraph elements
                paragraphs = article_body.find_elements(By.TAG_NAME, "p")
                # Filter out empty paragraphs and join with newlines
                full_text = "\n\n".join(p.text for p in paragraphs if p.text.strip())
                logger.info(f"Found article text with {len(paragraphs)} paragraphs ({len(full_text)} characters)")
            except NoSuchElementException:
                try:
                    # Fallback to ID selector
                    article_body = self.driver.find_element(By.ID, "article-body")
                    paragraphs = article_body.find_elements(By.TAG_NAME, "p")
                    full_text = "\n\n".join(p.text for p in paragraphs if p.text.strip())
                    logger.info(f"Found article text using ID selector with {len(paragraphs)} paragraphs ({len(full_text)} characters)")
                except NoSuchElementException:
                    logger.error("Could not find article body")
                    return None

            return {
                "title": title,
                "date": date,
                "author": author,
                "url": url,
                "full_text": full_text
            }

        except Exception as e:
            logger.error(f"Failed to scrape article {url}: {str(e)}")
            return None

    def scrape_articles(self) -> List[Dict]:
        """Main method to scrape all articles."""
        try:
            self.setup_driver()

            if not self.login():
                raise Exception("Login failed")

            article_links = self.get_article_links()
            scraped_articles = []

            for link in article_links:
                article_data = self.scrape_article(link)
                if article_data:
                    scraped_articles.append(article_data)

            return scraped_articles

        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            return []

        finally:
            if self.driver:
                self.driver.quit()

def main():
    # Get credentials from .env file
    username = os.getenv("FT_USERNAME")
    uni_id = os.getenv("FT_UNI_ID")
    password = os.getenv("FT_PASSWORD")
    if not username or not uni_id or not password:
        logger.error("FT_USERNAME, FT_UNI_ID and/or FT_PASSWORD not found in .env file")
        return

    # Create directory for scraped articles if it doesn't exist
    output_dir = "scraped_articles"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Created/verified output directory: {os.path.abspath(output_dir)}")

    scraper = FTScraper(username, uni_id, password)
    logger.info("Starting article scraping process...")
    articles = scraper.scrape_articles()
    logger.info(f"Found {len(articles)} articles to process")

    if not articles:
        logger.error("No articles were scraped. Check if login was successful and if articles were found.")
        return

    # Print results and save to files
    for i, article in enumerate(articles, 1):
        logger.info(f"Processing article {i} of {len(articles)}")
        print("\n" + "="*50)
        print(f"Title: {article['title']}")
        print(f"Date: {article['date']}")
        print(f"Author: {article['author']}")
        print(f"URL: {article['url']}")
        print(f"Text length: {len(article['full_text'])} characters")
        print("="*50)

        # Create a safe filename from the title
        safe_title = "".join(c for c in article['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{output_dir}/article_{i}_{safe_title[:50]}.txt"
        logger.info(f"Attempting to save article to: {filename}")

        try:
            # Save article to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Title: {article['title']}\n")
                f.write(f"Date: {article['date']}\n")
                f.write(f"Author: {article['author']}\n")
                f.write(f"URL: {article['url']}\n")
                f.write("\n" + "="*50 + "\n\n")
                f.write(article['full_text'])
            logger.info(f"Successfully saved article to: {filename}")
            print(f"Saved article to: {filename}")
        except Exception as e:
            logger.error(f"Failed to save article to {filename}: {str(e)}")

if __name__ == "__main__":
    main()

