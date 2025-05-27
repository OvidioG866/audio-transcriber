import logging
from transformers import pipeline
import numpy as np

logger = logging.getLogger(__name__)

class ArticlePrioritizer:
    def __init__(self):
        self.sentiment_analyzer = pipeline("sentiment-analysis")
        self.zero_shot_classifier = pipeline("zero-shot-classification")
        
        # Define categories for zero-shot classification
        self.categories = [
            "breaking news",
            "market analysis",
            "company news",
            "economic policy",
            "technology",
            "environment",
            "politics",
            "sports",
            "lifestyle"
        ]

    def analyze_sentiment(self, text):
        """
        Analyze the sentiment of the text
        
        Args:
            text (str): Text to analyze
            
        Returns:
            dict: Sentiment analysis results
        """
        try:
            # Truncate text if it's too long for the model
            truncated_text = text[:512] if len(text) > 512 else text
            
            result = self.sentiment_analyzer(truncated_text)[0]
            return {
                'label': result['label'],
                'score': result['score']
            }
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}")
            return None

    def classify_article(self, text):
        """
        Classify the article into predefined categories
        
        Args:
            text (str): Article text to classify
            
        Returns:
            dict: Classification results
        """
        try:
            # Truncate text if it's too long for the model
            truncated_text = text[:512] if len(text) > 512 else text
            
            result = self.zero_shot_classifier(
                truncated_text,
                candidate_labels=self.categories,
                multi_label=True
            )
            
            # Convert to a more readable format
            classifications = {
                label: score for label, score in zip(result['labels'], result['scores'])
            }
            
            return classifications
        except Exception as e:
            logger.error(f"Error in article classification: {str(e)}")
            return None

    def calculate_priority_score(self, article_data):
        """
        Calculate a priority score for the article
        
        Args:
            article_data (dict): Article data including text and metadata
            
        Returns:
            float: Priority score between 0 and 1
        """
        try:
            text = article_data.get('full_text', '')
            if not text:
                return 0.0
            
            # Get sentiment analysis
            sentiment = self.analyze_sentiment(text)
            if not sentiment:
                return 0.0
                
            # Get classification
            classification = self.classify_article(text)
            if not classification:
                return 0.0
            
            # Calculate base score from sentiment
            sentiment_score = 0.5
            if sentiment['label'] == 'POSITIVE':
                sentiment_score = 0.7
            elif sentiment['label'] == 'NEGATIVE':
                sentiment_score = 0.3
            
            # Calculate category score
            # Give higher weight to breaking news and market analysis
            category_weights = {
                'breaking news': 1.0,
                'market analysis': 0.9,
                'company news': 0.8,
                'economic policy': 0.7,
                'technology': 0.6,
                'environment': 0.5,
                'politics': 0.4,
                'sports': 0.3,
                'lifestyle': 0.2
            }
            
            category_score = max(
                score * category_weights.get(category, 0.5)
                for category, score in classification.items()
            )
            
            # Combine scores (70% category, 30% sentiment)
            final_score = (0.7 * category_score) + (0.3 * sentiment_score)
            
            return min(max(final_score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating priority score: {str(e)}")
            return 0.0

    def prioritize_articles(self, articles):
        """
        Prioritize a list of articles based on their content
        
        Args:
            articles (list): List of article dictionaries
            
        Returns:
            list: Sorted list of articles with priority scores
        """
        try:
            prioritized_articles = []
            
            for article in articles:
                priority_score = self.calculate_priority_score(article)
                article['priority_score'] = priority_score
                prioritized_articles.append(article)
            
            # Sort articles by priority score in descending order
            prioritized_articles.sort(key=lambda x: x['priority_score'], reverse=True)
            
            return prioritized_articles
            
        except Exception as e:
            logger.error(f"Error prioritizing articles: {str(e)}")
            return articles  # Return original list if prioritization fails 