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
        
        Args:
            prompt: Input prompt for text generation
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty (-2.0 to 2.0)
            presence_penalty: Presence penalty (-2.0 to 2.0)
            
        Returns:
            Generated text string
            
        Raises:
            Exception: If API call fails after retries
        """
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating text (attempt {attempt + 1}/{MAX_RETRIES})")
                logger.debug(f"Model: {model}, Max tokens: {max_tokens}")
                logger.debug(f"Prompt length: {len(prompt)} characters")
                
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
                        
                        logger.info(f"Text generated successfully ({len(generated_text)} characters)")
                        return generated_text
                    else:
                        raise Exception("No valid response in API result")
                
                elif response.status_code == 429:  # Rate limit
                    logger.warning("Rate limit exceeded, waiting before retry")
                    time.sleep(RETRY_DELAY * 2)
                    continue
                
                elif response.status_code == 401:
                    raise Exception("Invalid API key")
                
                else:
                    error_msg = f"API request failed with status {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg += f": {error_data['error'].get('message', 'Unknown error')}"
                    except:
                        pass
                    
                    logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                    
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                    else:
                        raise Exception(error_msg)
                        
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error on attempt {attempt + 1}: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Network error after {MAX_RETRIES} attempts: {str(e)}")
            
            except Exception as e:
                logger.warning(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Failed to generate text after {MAX_RETRIES} attempts: {str(e)}")
    
    def generate_completion(
        self,
        prompt: str,
        model: str = "gpt-3.5-turbo-instruct",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: Optional[List[str]] = None
    ) -> str:
        """
        Generate text completion using legacy completions endpoint
        
        Args:
            prompt: Input prompt
            model: OpenAI model (for completions endpoint)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            stop: Stop sequences
            
        Returns:
            Generated text string
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
        
        if stop:
            payload["stop"] = stop
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating completion (attempt {attempt + 1}/{MAX_RETRIES})")
                
                response = requests.post(
                    f"{self.base_url}/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        generated_text = data["choices"][0]["text"].strip()
                        
                        logger.info(f"Completion generated successfully ({len(generated_text)} characters)")
                        return generated_text
                    else:
                        raise Exception("No valid response in API result")
                
                else:
                    error_msg = f"API request failed with status {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg += f": {error_data['error'].get('message', 'Unknown error')}"
                    except:
                        pass
                    
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                    else:
                        raise Exception(error_msg)
                        
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Failed to generate completion after {MAX_RETRIES} attempts: {str(e)}")
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available OpenAI models
        
        Returns:
            List of model names
        """
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                models = [model["id"] for model in data.get("data", [])]
                logger.info(f"Retrieved {len(models)} available models")
                return sorted(models)
            else:
                logger.error(f"Failed to retrieve models: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving models: {str(e)}")
            return []
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation)
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters for English text
        return len(text) // 4

def main():
    """Command-line interface for OpenAI text generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenAI Text Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Text prompt for generation")
    parser.add_argument("--model", "-m", default="gpt-3.5-turbo", help="OpenAI model to use")
    parser.add_argument("--max-tokens", type=int, default=1000, help="Maximum tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7, help="Temperature (0.0-2.0)")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    
    args = parser.parse_args()
    
    try:
        client = OpenAIClient()
        
        if args.list_models:
            models = client.get_available_models()
            print("\nAvailable Models:")
            print("-" * 40)
            for model in models:
                print(f"  {model}")
            return 0
        
        # Generate text
        result = client.generate_text(
            prompt=args.prompt,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature
        )
        
        print("\n" + "="*50)
        print("GENERATED TEXT:")
        print("="*50)
        print(result)
        print("="*50)
        
        return 0
        
    except Exception as e:
        logger.error(f"Command-line execution failed: {str(e)}")
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
