"""
ElevenLabs Text-to-Speech Integration Script
Converts text to audio using ElevenLabs API and integrates with OpenAI script
"""
import os
import json
import logging
import time
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from elevenlabs import ElevenLabs, Voice, VoiceSettings, save
from config import *

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class ElevenLabsTTS:
    """ElevenLabs Text-to-Speech client with error handling and retry logic"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ElevenLabs TTS client
        
        Args:
            api_key: ElevenLabs API key (defaults to environment variable)
        """
        self.api_key = api_key or ELEVENLABS_API_KEY
        if not self.api_key:
            raise ValueError("ElevenLabs API key is required. Set ELEVENLABS_API_KEY environment variable.")
        
        self.client = ElevenLabs(api_key=self.api_key)
        self.available_voices = None
        
        logger.info("ElevenLabs TTS client initialized successfully")
    
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Retrieve available voices from ElevenLabs API
        
        Returns:
            List of available voices with their metadata
        """
        if self.available_voices is not None:
            return self.available_voices
        
        try:
            voices = self.client.voices.get_all()
            self.available_voices = [
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category,
                    "description": getattr(voice, 'description', ''),
                    "preview_url": getattr(voice, 'preview_url', '')
                }
                for voice in voices.voices
            ]
            logger.info(f"Retrieved {len(self.available_voices)} available voices")
            return self.available_voices
        except Exception as e:
            logger.error(f"Failed to retrieve voices: {str(e)}")
            return []
    
    def list_voices(self) -> None:
        """Print available voices to console"""
        voices = self.get_available_voices()
        if not voices:
            print("No voices available or failed to retrieve voices.")
            return
        
        print("\nAvailable Voices:")
        print("-" * 60)
        for voice in voices:
            print(f"ID: {voice['voice_id']}")
            print(f"Name: {voice['name']}")
            print(f"Category: {voice['category']}")
            if voice['description']:
                print(f"Description: {voice['description']}")
            print("-" * 60)
    
    def generate_audio(
        self,
        text: str,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        output_format: str = DEFAULT_OUTPUT_FORMAT
    ) -> bytes:
        """
        Generate audio from text using ElevenLabs API
        
        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            model_id: ElevenLabs model ID
            voice_settings: Voice configuration settings
            output_format: Audio output format
            
        Returns:
            Audio data as bytes
            
        Raises:
            Exception: If API call fails after retries
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Use default voice settings if none provided
        settings = voice_settings or DEFAULT_VOICE_SETTINGS
        
        # Create voice settings object
        voice_config = VoiceSettings(
            stability=settings.get("stability", 0.75),
            similarity_boost=settings.get("similarity_boost", 0.75),
            style=settings.get("style", 0.0),
            use_speaker_boost=settings.get("use_speaker_boost", True)
        )
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating audio (attempt {attempt + 1}/{MAX_RETRIES})")
                logger.debug(f"Text length: {len(text)} characters")
                logger.debug(f"Voice ID: {voice_id}, Model: {model_id}")
                
                # Generate audio using the ElevenLabs client's text-to-speech method
                audio_generator = self.client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id=model_id,
                    voice_settings=voice_config
                )
                
                # Convert generator to bytes
                audio_bytes = b"".join(audio_generator)
                logger.info(f"Audio generated successfully ({len(audio_bytes)} bytes)")
                return audio_bytes
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"All {MAX_RETRIES} attempts failed")
                    raise Exception(f"Failed to generate audio after {MAX_RETRIES} attempts: {str(e)}")
    
    def save_audio(
        self,
        audio_data: bytes,
        filename: Optional[str] = None,
        output_dir: Path = AUDIO_OUTPUT_DIR
    ) -> Path:
        """
        Save audio data to file
        
        Args:
            audio_data: Audio data as bytes
            filename: Output filename (auto-generated if None)
            output_dir: Output directory
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = int(time.time())
            filename = f"{AUDIO_FILE_PREFIX}_{timestamp}.mp3"
        
        # Ensure filename is safe and not too long
        filename = self._sanitize_filename(filename)
        
        output_path = output_dir / filename
        
        try:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            
            logger.info(f"Audio saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to save audio file: {str(e)}")
            raise
    
    def text_to_speech(
        self,
        text: str,
        output_filename: Optional[str] = None,
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        save_file: bool = True
    ) -> Optional[Path]:
        """
        Complete text-to-speech workflow
        
        Args:
            text: Text to convert
            output_filename: Output filename (auto-generated if None)
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration
            save_file: Whether to save audio to file
            
        Returns:
            Path to saved file if save_file=True, None otherwise
        """
        try:
            # Generate audio
            audio_data = self.generate_audio(
                text=text,
                voice_id=voice_id,
                voice_settings=voice_settings
            )
            
            if save_file:
                # Save to file
                return self.save_audio(audio_data, output_filename)
            else:
                return audio_data
                
        except Exception as e:
            logger.error(f"Text-to-speech conversion failed: {str(e)}")
            raise
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for filesystem compatibility
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(filename)
            filename = name[:MAX_FILENAME_LENGTH - len(ext)] + ext
        
        return filename

def main():
    """Command-line interface for ElevenLabs TTS"""
    parser = argparse.ArgumentParser(description="ElevenLabs Text-to-Speech Generator")
    parser.add_argument("--text", "-t", required=True, help="Text to convert to speech")
    parser.add_argument("--voice", "-v", default=DEFAULT_VOICE_ID, help="Voice ID to use")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--stability", type=float, default=0.75, help="Voice stability (0.0-1.0)")
    parser.add_argument("--similarity", type=float, default=0.75, help="Voice similarity boost (0.0-1.0)")
    parser.add_argument("--style", type=float, default=0.0, help="Voice style (0.0-1.0)")
    
    args = parser.parse_args()
    
    try:
        tts = ElevenLabsTTS()
        
        if args.list_voices:
            tts.list_voices()
            return
        
        # Custom voice settings from arguments
        voice_settings = {
            "stability": args.stability,
            "similarity_boost": args.similarity,
            "style": args.style,
            "use_speaker_boost": True
        }
        
        # Generate and save audio
        output_path = tts.text_to_speech(
            text=args.text,
            output_filename=args.output,
            voice_id=args.voice,
            voice_settings=voice_settings
        )
        
        print(f"Audio generated successfully: {output_path}")
        
    except Exception as e:
        logger.error(f"Command-line execution failed: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
