"""
Audio Generator - Integration between OpenAI and ElevenLabs
Combines OpenAI text generation with ElevenLabs audio synthesis
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from elevenlabs_tts import ElevenLabsTTS
from openAI import OpenAIClient
from config import *

logger = logging.getLogger(__name__)

class AudioGenerator:
    """Integrated audio generator using OpenAI and ElevenLabs"""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        elevenlabs_api_key: Optional[str] = None
    ):
        """
        Initialize Audio Generator with both APIs
        
        Args:
            openai_api_key: OpenAI API key
            elevenlabs_api_key: ElevenLabs API key
        """
        self.openai_client = OpenAIClient(api_key=openai_api_key)
        self.tts_client = ElevenLabsTTS(api_key=elevenlabs_api_key)
        
        logger.info("Audio Generator initialized with OpenAI and ElevenLabs clients")
    
    def generate_text_and_audio(
        self,
        prompt: str,
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        output_filename: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Union[str, Path]]:
        """
        Generate text using OpenAI and convert to audio using ElevenLabs
        
        Args:
            prompt: Input prompt for text generation
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration
            output_filename: Audio output filename
            max_tokens: Maximum tokens for OpenAI response
            temperature: OpenAI temperature setting
            
        Returns:
            Dictionary containing generated text and audio file path
        """
        try:
            logger.info("Starting text generation with OpenAI")
            
            # Generate text using OpenAI
            generated_text = self.openai_client.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            if not generated_text:
                raise ValueError("OpenAI generated empty or invalid text")
            
            logger.info(f"Generated text ({len(generated_text)} characters)")
            logger.debug(f"Text preview: {generated_text[:100]}...")
            
            # Convert text to audio using ElevenLabs
            logger.info("Converting text to audio with ElevenLabs")
            
            audio_path = self.tts_client.text_to_speech(
                text=generated_text,
                output_filename=output_filename,
                voice_id=voice_id,
                voice_settings=voice_settings
            )
            
            result = {
                "text": generated_text,
                "audio_path": audio_path,
                "prompt": prompt,
                "voice_id": voice_id
            }
            
            logger.info("Text-to-audio generation completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Text-to-audio generation failed: {str(e)}")
            raise
    
    def convert_existing_text_to_audio(
        self,
        text: str,
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Convert existing text to audio (bypass OpenAI generation)
        
        Args:
            text: Text to convert to audio
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration
            output_filename: Audio output filename
            
        Returns:
            Path to generated audio file
        """
        try:
            logger.info("Converting existing text to audio")
            
            audio_path = self.tts_client.text_to_speech(
                text=text,
                output_filename=output_filename,
                voice_id=voice_id,
                voice_settings=voice_settings
            )
            
            logger.info(f"Audio conversion completed: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Text-to-audio conversion failed: {str(e)}")
            raise
    
    def batch_generate_audio(
        self,
        texts: List[str],
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        output_prefix: str = "batch_audio"
    ) -> List[Dict[str, Union[str, Path]]]:
        """
        Generate audio for multiple texts
        
        Args:
            texts: List of texts to convert
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration
            output_prefix: Prefix for output filenames
            
        Returns:
            List of results with text and audio paths
        """
        results = []
        
        for i, text in enumerate(texts):
            try:
                logger.info(f"Processing batch item {i + 1}/{len(texts)}")
                
                output_filename = f"{output_prefix}_{i + 1:03d}.mp3"
                
                audio_path = self.convert_existing_text_to_audio(
                    text=text,
                    voice_id=voice_id,
                    voice_settings=voice_settings,
                    output_filename=output_filename
                )
                
                results.append({
                    "index": i + 1,
                    "text": text,
                    "audio_path": audio_path
                })
                
            except Exception as e:
                logger.error(f"Failed to process batch item {i + 1}: {str(e)}")
                results.append({
                    "index": i + 1,
                    "text": text,
                    "error": str(e)
                })
        
        logger.info(f"Batch processing completed: {len(results)} items processed")
        return results
    
    def get_voice_options(self) -> List[Dict[str, Any]]:
        """Get available voice options from ElevenLabs"""
        return self.tts_client.get_available_voices()
    
    def get_openai_models(self) -> List[str]:
        """Get available OpenAI models"""
        return self.openai_client.get_available_models()

def demo_workflow():
    """Demonstration of the complete workflow"""
    try:
        # Initialize audio generator
        generator = AudioGenerator()
        
        # Example prompt
        prompt = "Write a short story about a robot who discovers emotions for the first time."
        
        # Generate text and audio
        result = generator.generate_text_and_audio(
            prompt=prompt,
            voice_id=DEFAULT_VOICE_ID,
            max_tokens=500,
            temperature=0.8
        )
        
        print("=== Audio Generation Demo ===")
        print(f"Prompt: {result['prompt']}")
        print(f"Generated Text: {result['text'][:200]}...")
        print(f"Audio File: {result['audio_path']}")
        print(f"Voice Used: {result['voice_id']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Demo workflow failed: {str(e)}")
        print(f"Demo failed: {str(e)}")
        return None

if __name__ == "__main__":
    # Run demonstration
    demo_workflow()
