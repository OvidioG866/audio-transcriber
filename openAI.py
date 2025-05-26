"""
OpenAI API Integration Script
Handles text generation using OpenAI's GPT models
"""
import os
import logging
import json
from typing import Optional, List, Dict, Any
import requests
from config import OPENAI_API_KEY, MAX_RETRIES, RETRY_DELAY
import time

logger = logging.getLogger(__name__)

class OpenAIClient:
    """OpenAI API client for text generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI client
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print("✅ OpenAI client initialized successfully")
        logger.info("OpenAI client initialized successfully")
    
    def generate_text(
        self,
        prompt: str,
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0
    ) -> str:
        """
        Generate text using OpenAI API
        """
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        generated_text = data["choices"][0]["message"]["content"].strip()
                        return generated_text
                    else:
                        raise Exception("No valid response in API result")
                
                elif response.status_code == 429:
                    time.sleep(RETRY_DELAY * 2)
                    continue
                elif response.status_code == 401:
                    raise Exception("Invalid API key")
                else:
                    error_msg = f"API request failed with status {response.status_code}"
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                    else:
                        raise Exception(error_msg)
                        
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Network error after {MAX_RETRIES} attempts: {str(e)}")
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Failed to generate text after {MAX_RETRIES} attempts: {str(e)}")
    
    def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models"""
        try:
            response = requests.get(f"{self.base_url}/models", headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                models = [model["id"] for model in data.get("data", [])]
                return sorted(models)
            else:
                return []
        except Exception as e:
            return []

def read_article(file_path):
    """Read and parse article content from a text file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Assuming first line is title and rest is excerpt
    title, excerpt = content.split('\n', 1)
    return title.strip(), excerpt.strip()

def generate_podcast_script(title, content):
    """Generate podcast script using OpenAI API."""
    try:
        # Initialize the OpenAI client
        client = OpenAIClient()
        
        prompt = f"""Write a concise, spoken-style summary suitable for audio narration. The tone should be informative, slightly conversational, use data if provided. Keep the total output under 1200 characters. Do not use introductionary words such as "headline" or "context".

Article Title: {title}
Article Content: {content}

Structure:
- Brief headline rephrasing (1 sentence).
- Context (1–2 sentences).
- Main point breakdown (2–4 sentences).
- Possible consequences (1 sentence)."""

        script = client.generate_text(
            prompt=prompt,
            model="gpt-3.5-turbo",
            max_tokens=300,
            temperature=0.7
        )
        
        logger.info(f"Generated script for article: {title[:50]}...")
        return script

    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        raise

def main():
    # Process only the first article file
    article_files = glob.glob("scraped_articles/*.txt")
    if not article_files:
        print("No article files found in scraped_articles directory")
        return

    article_file = article_files[0]
    print(f"Processing test article: {article_file}")

    # Read article
    title, excerpt = read_article(article_file)

    # Generate podcast script
    try:
        script = generate_podcast_script(title, excerpt)
        print("\nGenerated script:")
        print("-"*30)
        print(script)
        print("-"*30)
        print(f"Character count: {len(script)}")

        # Save the script to a file
        with open("generated_script.txt", "w", encoding="utf-8") as f:
            f.write(script)
        print("\nScript saved to generated_script.txt")
    except Exception as e:
        print(f"Error generating script: {str(e)}")

if __name__ == "__main__":
    main()
