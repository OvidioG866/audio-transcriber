from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class FTScraper:
    def __init__(self, username: str, uni_id: str, password: str):
        self.username = username
        self.uni_id = uni_id
        self.password = password
        self.driver = None
        self.is_logged_in = False
        self.last_login_time = None
        self.visited_urls = set()
        self._load_visited_urls()

    def _load_visited_urls(self):
        """Load previously visited URLs from file"""
        try:
            if os.path.exists('visited_urls.json'):
                with open('visited_urls.json', 'r') as f:
                    self.visited_urls = set(json.load(f))
        except Exception as e:
            logger.error(f"Error loading visited URLs: {str(e)}")

    def _save_visited_urls(self):
        """Save visited URLs to file"""
        try:
            with open('visited_urls.json', 'w') as f:
                json.dump(list(self.visited_urls), f)
        except Exception as e:
            logger.error(f"Error saving visited URLs: {str(e)}")

    async def initialize(self):
        """Initialize the Chrome driver with async support"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Add user agent to avoid detection
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            return False

    async def login(self) -> bool:
        """Login to FT with async support"""
        try:
            if not self.driver:
                if not await self.initialize():
                    return False

            # Check if we're already logged in
            if self.is_logged_in and self.last_login_time:
                time_since_login = datetime.now() - self.last_login_time
                if time_since_login.total_seconds() < 3600:  # Less than 1 hour
                    logger.info("Session still valid, skipping login")
                    return True

            # Navigate to login page
            await asyncio.to_thread(self.driver.get, "https://www.ft.com/signin")
            
            # Wait for and fill in login form
            await asyncio.to_thread(
                WebDriverWait(self.driver, 10).until,
                EC.presence_of_element_located((By.ID, "enter-email"))
            ).send_keys(self.username)

            await asyncio.to_thread(
                self.driver.find_element,
                By.CSS_SELECTOR,
                "button[type='submit']"
            ).click()

            # Wait for and fill in institution ID
            await asyncio.to_thread(
                WebDriverWait(self.driver, 10).until,
                EC.presence_of_element_located((By.ID, "enter-institution-id"))
            ).send_keys(self.uni_id)

            await asyncio.to_thread(
                self.driver.find_element,
                By.CSS_SELECTOR,
                "button[type='submit']"
            ).click()

            # Wait for and fill in password
            await asyncio.to_thread(
                WebDriverWait(self.driver, 10).until,
                EC.presence_of_element_located((By.ID, "enter-password"))
            ).send_keys(self.password)

            await asyncio.to_thread(
                self.driver.find_element,
                By.CSS_SELECTOR,
                "button[type='submit']"
            ).click()

            # Wait for successful login
            await asyncio.to_thread(
                WebDriverWait(self.driver, 10).until,
                EC.presence_of_element_located((By.CSS_SELECTOR, ".o-header__nav"))
            )

            self.is_logged_in = True
            self.last_login_time = datetime.now()
            logger.info("Successfully logged in to FT")
            return True

        except TimeoutException:
            logger.error("Timeout during login process")
            return False
        except WebDriverException as e:
            logger.error(f"WebDriver error during login: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            return False

    async def scrape_articles(self) -> List[Dict]:
        """Scrape article previews with async support"""
        try:
            if not await self.login():
                return []

            sections = [
                "https://www.ft.com/myft/following",
                "https://www.ft.com/markets",
                "https://www.ft.com/technology",
                "https://www.ft.com/opinion",
                "https://www.ft.com/world"
            ]

            all_previews = []
            for section in sections:
                try:
                    await asyncio.to_thread(self.driver.get, section)
                    await asyncio.sleep(2)  # Allow dynamic content to load

                    # Wait for articles to load
                    articles = await asyncio.to_thread(
                        WebDriverWait(self.driver, 10).until,
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article"))
                    )

                    for article in articles:
                        try:
                            headline = await asyncio.to_thread(
                                article.find_element,
                                By.CSS_SELECTOR,
                                "h3, .o-teaser__heading"
                            ).text

                            url = await asyncio.to_thread(
                                article.find_element,
                                By.CSS_SELECTOR,
                                "a"
                            ).get_attribute("href")

                            if url in self.visited_urls:
                                continue

                            standfirst = ""
                            try:
                                standfirst = await asyncio.to_thread(
                                    article.find_element,
                                    By.CSS_SELECTOR,
                                    ".o-teaser__standfirst"
                                ).text
                            except:
                                pass

                            all_previews.append({
                                "headline": headline,
                                "url": url,
                                "standfirst": standfirst
                            })

                            self.visited_urls.add(url)

                        except Exception as e:
                            logger.error(f"Error processing article preview: {str(e)}")
                            continue

                except Exception as e:
                    logger.error(f"Error scraping section {section}: {str(e)}")
                    continue

            self._save_visited_urls()
            return all_previews

        except Exception as e:
            logger.error(f"Error in scrape_articles: {str(e)}")
            return []

    async def scrape_full_article(self, url: str, is_initial_scrape: bool = False) -> Optional[Dict]:
        """Scrape full article content with async support"""
        try:
            if not self.is_logged_in and not await self.login():
                return None

            await asyncio.to_thread(self.driver.get, url)
            await asyncio.sleep(3)  # Wait for dynamic content

            # Check for paywall
            paywall_selectors = [
                ".o-topper__paywall",
                ".o-topper__premium",
                ".o-topper__locked"
            ]
            
            for selector in paywall_selectors:
                try:
                    if await asyncio.to_thread(
                        self.driver.find_element,
                        By.CSS_SELECTOR,
                        selector
                    ):
                        logger.warning(f"Article is behind paywall: {url}")
                        return None
                except:
                    continue

            # Get article content
            title = await asyncio.to_thread(
                WebDriverWait(self.driver, 10).until,
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
            ).text

            # Try multiple selectors for article body
            content_selectors = [
                ".article__content",
                ".article__body",
                ".o-topper__content",
                ".o-topper__standfirst"
            ]

            full_text = ""
            for selector in content_selectors:
                try:
                    elements = await asyncio.to_thread(
                        self.driver.find_elements,
                        By.CSS_SELECTOR,
                        selector
                    )
                    if elements:
                        full_text = " ".join([await asyncio.to_thread(e.text) for e in elements])
                        break
                except:
                    continue

            if not full_text:
                logger.error(f"Could not find article content: {url}")
                return None

            # Get metadata
            date = None
            try:
                date_str = await asyncio.to_thread(
                    self.driver.find_element,
                    By.CSS_SELECTOR,
                    "time"
                ).get_attribute("datetime")
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except:
                pass

            author = None
            try:
                author = await asyncio.to_thread(
                    self.driver.find_element,
                    By.CSS_SELECTOR,
                    ".o-topper__author"
                ).text
            except:
                pass

            return {
                "title": title,
                "full_text": full_text,
                "date": date,
                "author": author
            }

        except TimeoutException:
            logger.error(f"Timeout scraping article: {url}")
            return None
        except WebDriverException as e:
            logger.error(f"WebDriver error scraping article {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error scraping article {url}: {str(e)}")
            return None

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                await asyncio.to_thread(self.driver.quit)
                self.driver = None
            self.is_logged_in = False
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def force_cleanup(self):
        """Force cleanup of all resources"""
        try:
            await self.cleanup()
            self.visited_urls.clear()
            self._save_visited_urls()
        except Exception as e:
            logger.error(f"Error during force cleanup: {str(e)}") 