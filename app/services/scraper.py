import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

class FTScraper:
    def __init__(self, username, uni_id, password):
        self.username = username
        self.uni_id = uni_id
        self.password = password
        self.driver = None
        self.is_logged_in = False
        self._initialize_driver()

    def _initialize_driver(self):
        """Initialize the Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)

    def login(self):
        """Login to FT"""
        try:
            self.driver.get('https://www.ft.com/signin')
            
            # Wait for and click the institutional login button
            institutional_login = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-trackable="institutional-login"]'))
            )
            institutional_login.click()
            
            # Wait for and fill in the institutional ID
            uni_id_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'institutionId'))
            )
            uni_id_input.send_keys(self.uni_id)
            
            # Click continue
            continue_button = self.driver.find_element(By.CSS_SELECTOR, '[data-trackable="continue"]')
            continue_button.click()
            
            # Wait for and fill in username and password
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'username'))
            )
            password_input = self.driver.find_element(By.ID, 'password')
            
            username_input.send_keys(self.username)
            password_input.send_keys(self.password)
            
            # Click sign in
            sign_in_button = self.driver.find_element(By.CSS_SELECTOR, '[data-trackable="sign-in"]')
            sign_in_button.click()
            
            # Wait for successful login
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-trackable="my-account"]'))
            )
            
            self.is_logged_in = True
            logger.info("Successfully logged in to FT")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            return False

    def refresh_session_if_needed(self):
        """Check if session is valid and refresh if needed"""
        if not self.is_logged_in:
            return self.login()
        
        try:
            self.driver.get('https://www.ft.com/myaccount')
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-trackable="my-account"]'))
            )
            return True
        except:
            logger.info("Session expired, logging in again...")
            return self.login()

    def scrape_articles(self):
        """Scrape article previews from FT"""
        try:
            self.driver.get('https://www.ft.com/')
            
            # Wait for articles to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.js-teaser'))
            )
            
            # Get all article previews
            articles = []
            previews = self.driver.find_elements(By.CSS_SELECTOR, '.js-teaser')
            
            for preview in previews[:10]:  # Limit to 10 articles for now
                try:
                    headline = preview.find_element(By.CSS_SELECTOR, '.js-teaser-heading-link').text
                    url = preview.find_element(By.CSS_SELECTOR, '.js-teaser-heading-link').get_attribute('href')
                    
                    try:
                        standfirst = preview.find_element(By.CSS_SELECTOR, '.js-teaser-standfirst').text
                    except NoSuchElementException:
                        standfirst = None
                    
                    articles.append({
                        'headline': headline,
                        'url': url,
                        'standfirst': standfirst
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing article preview: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error scraping articles: {str(e)}")
            return None

    def scrape_full_article(self, url):
        """Scrape the full content of an article"""
        try:
            self.driver.get(url)
            
            # Wait for article content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.article__content'))
            )
            
            # Get article content
            content = self.driver.find_element(By.CSS_SELECTOR, '.article__content').text
            
            # Get article metadata
            try:
                date = self.driver.find_element(By.CSS_SELECTOR, '.article__timestamp').text
            except NoSuchElementException:
                date = None
                
            try:
                author = self.driver.find_element(By.CSS_SELECTOR, '.article__author-name').text
            except NoSuchElementException:
                author = None
            
            return {
                'full_text': content,
                'date': date,
                'author': author
            }
            
        except Exception as e:
            logger.error(f"Error scraping full article: {str(e)}")
            return None

    def cleanup(self):
        """Clean up resources but keep the session alive"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.is_logged_in = False

    def force_cleanup(self):
        """Force cleanup of all resources including the browser"""
        self.cleanup() 