from dataclasses import dataclass
from typing import List, Dict, Tuple
import re
from collections import defaultdict
import os
import logging

logger = logging.getLogger(__name__)

@dataclass
class Article:
    title: str
    content: str
    original_position: int
    url: str = ""
    summary: str = ""
    score: float = 0.0

class GeopoliticalPrioritizer:
    def __init__(self):
        # Define categories and their keywords
        self.categories = {
            "Military": {
                "weight": 1.0,
                "keywords": [
                    # General military terms
                    "military", "defense", "armed forces", "security", "militia", "militant", "defence",
                    # Conflict and warfare
                    "war", "conflict", "combat", "battle", "hostilities", "invasion", "attack", "strike",
                    "operation", "troop movements", "cyberwarfare", "cyber warfare",
                    # Military branches and personnel
                    "army", "navy", "air force", "troops", "soldiers", "soldier",
                    # Weapons and equipment
                    "weapon", "weapons", "missile", "missiles", "tank", "tanks", "artillery", "howitzer",
                    "drone", "drones", "unmanned aerial vehicle", "UAV", "fighter jet", "helicopter",
                    "submarine", "anti-aircraft gun", "anti-tank missile", "guided missile",
                    # Specific weapons
                    "rifle", "assault rifle", "AK-47", "M16", "sniper rifle", "machine gun", "grenade",
                    "rocket launcher", "bazooka", "pistol", "handgun", "carbine", "machine pistol",
                    # Advanced weapons
                    "nuclear weapon", "chemical weapon", "biological weapon", "explosive", "cluster bomb",
                    "landmine", "bomb", "torpedo", "surface-to-air missile", "SAM", "intercontinental ballistic missile",
                    "ICBM", "grenade launcher",
                    # Intelligence
                    "spy", "sping", "intelligence", "secret service", "cia", "mi6", "nato"
                    # Countries of interest
                    "italy", "italia", "italian", "taiwan", "palestine", "gaza", "fed"
                ]
            },
            "Energy": {
                "weight": 0.9,
                "keywords": [
                    # General energy terms
                    "energy", "power", "electricity", "electric grid", "energy security", "energy supply",
                    "energy crisis", "energy prices", "energy independence",
                    # Energy sources
                    "oil", "gas", "natural gas", "fossil fuel", "fossil fuels", "coal", "nuclear",
                    "renewable", "solar", "wind power", "hydropower",
                    # Infrastructure
                    "pipeline", "power plant", "refinery", "drilling",
                    # Organizations and companies
                    "OPEC", "ExxonMobil", "Chevron", "BP", "Shell", "TotalEnergies", "Gazprom",
                    "Saudi Aramco", "PetroChina", "Rosneft", "Equinor", "CNOOC", "Repsol"
                ]
            },
            "Food & Mineral Supply": {
                "weight": 0.8,
                "keywords": [
                    # Food security
                    "wheat", "grain", "food security", "agriculture",
                    # Minerals and resources
                    "minerals", "rare earth", "lithium", "cobalt", "nickel", "copper",
                    "natural resources", "mining",
                    # Supply chain
                    "supply chain", "commodities", "exports", "imports",
                    # Migrants
                    "migrants", "asylum" 
                    # Dictators
                    "putin", "iran", "china", "russia", "israel", "netanyahu", "hizbollah", "turkey"
                ]
            },
            "Tech & Innovation": {
                "weight": 0.7,
                "keywords": [
                    # General tech terms
                    "technology", "tech", "innovation", "R&D", "startup", "digital", "automation",
                    # AI and computing
                    "AI", "artificial intelligence", "machine learning", "quantum computing",
                    "semiconductor", "chip", "chips", "robotics", "blockchain", "big data",
                    # Infrastructure
                    "software", "hardware", "cloud computing", "cybersecurity", "data center",
                    "5G", "6G",
                    # Companies
                    "tech giants", "Intel", "AMD", "NVIDIA", "TSMC", "Qualcomm", "Samsung Electronics",
                    "IBM", "Google", "Microsoft", "Apple", "Facebook", "Meta", "Amazon", "Tesla",
                    "ASML", "Broadcom", "Micron"
                ]
            },
            "Economy": {
                "weight": 0.6,
                "keywords": [
                    # Economic indicators
                    "GDP", "inflation", "inflation rate", "deflation", "unemployment",
                    "economic growth", "economic downturn", "economic recovery", "recession",
                    # Policy and markets
                    "fiscal policy", "monetary policy", "trade balance", "stimulus",
                    "consumer spending", "investment", "economic indicators",
                    # Industry metrics
                    "supply chain", "manufacturing output", "retail sales"
                ]
            },
            "Elections & Regime Change": {
                "weight": 0.5,
                "keywords": [
                    # Political processes
                    "election", "vote", "ballot", "poll", "campaign", "democratic process",
                    # Government and leadership
                    "regime", "regime change", "government", "transition", "parliament",
                    "prime minister", "president", "governance",
                    # Political stability
                    "political", "political party", "political instability", "political unrest",
                    "protest", "revolution", "civil unrest", "coup", "authoritarian"
                

                ]
            },
            "Bond Markets": {
                "weight": 0.4,
                "keywords": [
                    # Market terms
                    "bonds", "bond market", "yield", "yield curve", "treasury", "government bonds",
                    "corporate bonds", "junk bonds", "investment grade", "tresuries",
                    # Risk and analysis
                    "liquidity", "credit risk", "default risk", "interest rate", "bond yields",
                    "spread", "fixed income", "debt market",
                    # Market operations
                    "bond issuance", "coupon", "maturity"
                ]
            },
            "Central Banks": {
                "weight": 0.3,
                "keywords": [
                    # General terms
                    "central bank", "monetary policy", "inflation target", "policy statement",
                    "balance sheet", "open market operations",
                    # Interest rates
                    "interest rate", "rate hike", "rate cut", "repo rate", "discount rate",
                    # Monetary operations
                    "quantitative easing", "QE", "monetary tightening",
                    # Major central banks
                    "Federal Reserve", "ECB", "Bank of England", "Bank of Japan"
                ]
            },
            "Currency/Crypto/Commodity Shocks": {
                "weight": 0.2,
                "keywords": [
                    # Currency markets
                    "currency", "forex", "exchange rate", "foreign exchange market",
                    "currency devaluation", "USD", "EUR", "JPY", "GBP", "CNY", "CHF", "CAD", "AUD",
                    # Cryptocurrency
                    "crypto", "cryptocurrency", "bitcoin", "ethereum", "digital asset",
                    "crypto regulation", "crypto market", "Bitcoin", "Ethereum", "Ripple", "Litecoin",
                    "Cardano", "Polkadot", "Dogecoin", "Binance Coin", "Tether", "Solana",
                    # Commodities
                    "commodity", "commodities", "gold", "silver", "crude oil", "natural gas",
                    "copper", "platinum", "palladium", "commodity prices",
                    # Market conditions
                    "volatility", "hedging", "price shock", "market turbulence"
                ]
            },
            "Sanctions & Trade Policy": {
                "weight": 0.15,
                "keywords": [
                    # Trade terms
                    "trade policy", "trade agreement", "WTO", "customs", "quota",
                    "trade war", "trade barriers", "import tariffs", "export restrictions",
                    "retaliatory tariffs", "geopolitical sanctions",
                    # Sanctions
                    "sanctions", "embargo", "export control", "import restrictions",
                    "economic sanctions", "blacklist", "economic pressure"
                ]
            },
            "Diplomacy & Alliances": {
                "weight": 0.1,
                "keywords": [
                    # General terms
                    "diplomacy", "alliance", "coalition", "treaty", "summit", "negotiation",
                    "foreign policy", "international relations", "power bloc",
                    # Relations
                    "bilateral relations", "multilateral", "strategic partnership",
                    "diplomatic talks", "diplomatic mission", "peace talks",
                    # Organizations
                    "UN", "NATO", "G7", "G20",
                    # Personnel
                    "ambassador"
                ]
            },
            "Big Tech": {
                "weight": 0.05,
                "keywords": [
                    # Companies
                    "big tech", "Facebook", "Meta", "Google", "Alphabet", "Apple", "Amazon",
                    "Microsoft", "Tesla", "Netflix", "Twitter", "LinkedIn", "YouTube",
                    # Services and platforms
                    "cloud services", "AI platform", "social media", "digital advertising",
                    # Regulation and privacy
                    "data privacy", "antitrust", "platform regulation"
                ]
            }
        }

    def _count_keyword_matches(self, text: str, keywords: List[str]) -> int:
        """Count how many keywords appear in the text."""
        text = text.lower()
        return sum(1 for keyword in keywords if keyword.lower() in text)

    def _calculate_keyword_score(self, article: Article) -> float:
        """Calculate score based on keyword matches."""
        total_score = 0.0
        for category, data in self.categories.items():
            keyword_matches = self._count_keyword_matches(
                f"{article.title} {article.content}",
                data["keywords"]
            )
            category_score = keyword_matches * data["weight"]
            total_score += category_score
        return total_score

    def _calculate_source_score(self, article: Article) -> float:
        """Calculate source score based on article source."""
        # This method needs to be implemented based on the actual implementation
        return 0.0

    def _calculate_topic_score(self, article: Article) -> float:
        """Calculate topic score based on article topic."""
        # This method needs to be implemented based on the actual implementation
        return 0.0

    def _calculate_length_score(self, article: Article) -> float:
        """Calculate length score based on article length."""
        # This method needs to be implemented based on the actual implementation
        return 0.0

    def prioritize_articles(self, articles: List[Article]) -> List[Article]:
        """Prioritize articles based on various factors."""
        if not articles:
            return []

        total_articles = len(articles)
        logger.info(f"Prioritizing {total_articles} articles")

        for i, article in enumerate(articles):
            # Calculate base score from keywords
            base_score = self._calculate_keyword_score(article)
            
            # Calculate source score
            source_score = self._calculate_source_score(article)
            
            # Calculate topic score
            topic_score = self._calculate_topic_score(article)
            
            # Calculate length score
            length_score = self._calculate_length_score(article)
            
            # Calculate final score with weights (adjusted to remove recency)
            final_score = (
                base_score * 0.4 +  # Increased from 0.3 to 0.4
                source_score * 0.25 +  # Increased from 0.2 to 0.25
                topic_score * 0.2 +  # Increased from 0.15 to 0.2
                length_score * 0.15  # Increased from 0.1 to 0.15
            )
            
            article.score = final_score
            logger.debug(f"Article '{article.title}' scored {final_score:.2f}")

        # Sort articles by score in descending order
        sorted_articles = sorted(articles, key=lambda x: x.score, reverse=True)
        
        # Log all articles with their scores
        logger.info("\nAll articles by priority:")
        for i, article in enumerate(sorted_articles, 1):
            logger.info(f"{i}. Score: {article.score:.2f} - {article.title[:100]}...")
        
        return sorted_articles

def read_articles_from_folder(folder_path: str) -> List[Article]:
    """
    Read articles from the scraped_articles folder.

    Args:
        folder_path: Path to the folder containing article files

    Returns:
        List of Article objects
    """
    articles = []

    # Get all article files and sort them by their position number
    # Exclude priority list files and only get actual article files
    article_files = [
        f for f in os.listdir(folder_path) 
        if f.startswith('article_') and not f.startswith('article_priority_')
    ]
    
    # Sort files by their position number, handling potential errors
    def get_position(filename):
        try:
            return int(filename.split('_')[1])
        except (IndexError, ValueError):
            return float('inf')  # Put files with invalid positions at the end
    
    article_files.sort(key=get_position)

    for file_name in article_files:
        file_path = os.path.join(folder_path, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title, URL, and summary
            lines = content.split('\n')
            title = ""
            url = ""
            summary = ""
            content_lines = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('Title: '):
                    title = line[7:].strip()
                elif line.startswith('URL: '):
                    url = line[5:].strip()
                elif line.startswith('Summary: '):
                    summary = line[9:].strip()
                elif line != '='*50:  # Skip the separator line
                    content_lines.append(line)
            
            article_content = '\n'.join(content_lines).strip()

            # Extract position from filename (e.g., "article_1_" -> 1)
            try:
                position = int(file_name.split('_')[1])
            except (IndexError, ValueError):
                logger.warning(f"Could not extract position from filename: {file_name}")
                position = len(articles) + 1

            articles.append(Article(
                title=title,
                content=article_content,
                original_position=position,
                url=url,
                summary=summary
            ))

        except Exception as e:
            logger.error(f"Error reading file {file_name}: {str(e)}")

    return articles

def main():
    # Example usage
    prioritizer = GeopoliticalPrioritizer()

    # Read articles from the scraped_articles folder
    articles = read_articles_from_folder('scraped_articles')

    if not articles:
        print("No articles found in the scraped_articles folder.")
        return

    # Prioritize articles
    ranked_articles = prioritizer.prioritize_articles(articles)

    # Print results
    print("\nRanked Articles by Geopolitical Priority:")
    print("-" * 50)
    for i, article in enumerate(ranked_articles, 1):
        print(f"\n{i}. Score: {article.score:.2f}")
        print(f"Title: {article.title}")
        print(f"Original Position: {article.original_position}")
        print(f"Content Preview: {article.content[:200]}...")

if __name__ == "__main__":
    main()
