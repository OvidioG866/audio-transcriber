from dataclasses import dataclass
from typing import List, Dict, Tuple
import re
from collections import defaultdict
import os

@dataclass
class Article:
    title: str
    content: str
    original_position: int
    score: float = 0.0

class GeopoliticalPrioritizer:
    def __init__(self):
        # Define categories and their keywords
        self.categories = {
            "Military": {
                "weight": 1.0,
                "keywords": [
                    # General military terms
                    "military", "defense", "armed forces", "security", "militia",
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
                    "ICBM", "grenade launcher"
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
                    "supply chain", "commodities", "exports", "imports"
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
                    "corporate bonds", "junk bonds", "investment grade",
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

    def _calculate_position_score(self, position: int, total_articles: int) -> float:
        """Calculate score based on article position (earlier = higher score)."""
        return 1.0 - (position / total_articles)

    def prioritize_articles(self, articles: List[Tuple[str, str, int]]) -> List[Article]:
        """
        Prioritize articles based on category matches and position.

        Args:
            articles: List of tuples containing (title, content, original_position)

        Returns:
            List of Article objects sorted by score
        """
        processed_articles = []
        total_articles = len(articles)

        for title, content, position in articles:
            article = Article(title=title, content=content, original_position=position)
            total_score = 0.0

            # Calculate category scores
            for category, data in self.categories.items():
                keyword_matches = self._count_keyword_matches(
                    f"{title} {content}",
                    data["keywords"]
                )
                category_score = keyword_matches * data["weight"]
                total_score += category_score

            # Add position score (weighted at 20% of total)
            position_score = self._calculate_position_score(position, total_articles)
            total_score += position_score * 0.2

            article.score = total_score
            processed_articles.append(article)

        # Sort articles by score in descending order
        return sorted(processed_articles, key=lambda x: x.score, reverse=True)

def read_articles_from_folder(folder_path: str) -> List[Tuple[str, str, int]]:
    """
    Read articles from the scraped_articles folder.

    Args:
        folder_path: Path to the folder containing article files

    Returns:
        List of tuples containing (title, content, original_position)
    """
    articles = []

    # Get all article files and sort them by their position number
    article_files = [f for f in os.listdir(folder_path) if f.startswith('article_')]
    article_files.sort(key=lambda x: int(x.split('_')[1]))

    for file_name in article_files:
        file_path = os.path.join(folder_path, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title and content
            # Assuming first line is title and rest is content
            lines = content.split('\n')
            title = lines[0].strip()
            article_content = '\n'.join(lines[1:]).strip()

            # Extract position from filename (e.g., "article_1_" -> 1)
            position = int(file_name.split('_')[1])

            articles.append((title, article_content, position))

        except Exception as e:
            print(f"Error reading file {file_name}: {str(e)}")

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
