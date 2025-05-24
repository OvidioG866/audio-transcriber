"""
UnrealSpeech Text-to-Speech Integration Script
Converts text to audio using UnrealSpeech API
"""
import os
import json
import logging
import time
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
from config import *

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

class UnrealSpeechTTS:
    """UnrealSpeech Text-to-Speech client with error handling and retry logic"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize UnrealSpeech TTS client
        
        Args:
            api_key: UnrealSpeech API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv("UNREALSPEECH_API_KEY")
        if not self.api_key:
            raise ValueError("UnrealSpeech API key is required. Set UNREALSPEECH_API_KEY environment variable.")
        
        self.base_url = "https://api.v8.unrealspeech.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print("✅ UnrealSpeech TTS client initialized successfully")
        logger.info("UnrealSpeech TTS client initialized successfully")
    
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Retrieve available voices from UnrealSpeech API
        
        Returns:
            List of available voices with their metadata
        """
        try:
            response = requests.get(
                f"{self.base_url}/voices",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                voices_data = response.json()
                logger.info(f"Retrieved {len(voices_data)} available voices")
                return voices_data
            else:
                logger.error(f"Failed to retrieve voices: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to retrieve voices: {str(e)}")
            return []
    
    def list_voices(self) -> None:
        """Print available voices to console"""
        voices = self.get_available_voices()
        if not voices:
            print("No voices available or failed to retrieve voices.")
            return
        
        print("\nAvailable UnrealSpeech Voices:")
        print("-" * 60)
        for voice in voices:
            print(f"Voice ID: {voice.get('voice_id', 'N/A')}")
            print(f"Name: {voice.get('name', 'N/A')}")
            print(f"Language: {voice.get('language', 'N/A')}")
            print(f"Gender: {voice.get('gender', 'N/A')}")
            print("-" * 60)
    
    def generate_audio(
        self,
        text: str,
        voice_id: str = "Scarlett",
        bitrate: str = "192k",
        speed: float = 0.0,
        pitch: float = 1.0,
        codec: str = "libmp3lame"
    ) -> bytes:
        """
        Generate audio from text using UnrealSpeech API
        
        Args:
            text: Text to convert to speech
            voice_id: UnrealSpeech voice ID
            bitrate: Audio bitrate (128k, 192k, 256k, 320k)
            speed: Speech speed (-1.0 to 1.0)
            pitch: Speech pitch (0.5 to 2.0)
            codec: Audio codec (libmp3lame, pcm_mulaw, pcm_alaw)
            
        Returns:
            Audio data as bytes
            
        Raises:
            Exception: If API call fails after retries
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        payload = {
            "Text": text,
            "VoiceId": voice_id,
            "Bitrate": bitrate,
            "Speed": speed,
            "Pitch": pitch,
            "Codec": codec
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"🎵 Generating audio with UnrealSpeech (attempt {attempt + 1})...")
                logger.info(f"Generating audio (attempt {attempt + 1}/{MAX_RETRIES})")
                logger.debug(f"Text length: {len(text)} characters")
                logger.debug(f"Voice ID: {voice_id}, Bitrate: {bitrate}")
                
                response = requests.post(
                    f"{self.base_url}/stream",
                    headers=self.headers,
                    json=payload,
                    timeout=120
                )
                
                if response.status_code == 200:
                    audio_bytes = response.content
                    print(f"✅ Audio generated successfully ({len(audio_bytes)} bytes)")
                    logger.info(f"Audio generated successfully ({len(audio_bytes)} bytes)")
                    return audio_bytes
                
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
                            error_msg += f": {error_data['error']}"
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
        
        # Ensure output directory exists
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / filename
        
        try:
            print(f"💾 Saving audio file to: {output_path}")
            with open(output_path, "wb") as f:
                f.write(audio_data)
            
            print(f"✅ Audio file saved successfully: {output_path}")
            logger.info(f"Audio saved to: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Failed to save audio file: {str(e)}")
            logger.error(f"Failed to save audio file: {str(e)}")
            raise
    
    def text_to_speech(
        self,
        text: str,
        output_filename: Optional[str] = None,
        voice_id: str = "Scarlett",
        bitrate: str = "192k",
        speed: float = 0.0,
        pitch: float = 1.0,
        save_file: bool = True
    ) -> Optional[Path]:
        """
        Complete text-to-speech workflow
        
        Args:
            text: Text to convert
            output_filename: Output filename (auto-generated if None)
            voice_id: UnrealSpeech voice ID
            bitrate: Audio bitrate
            speed: Speech speed
            pitch: Speech pitch
            save_file: Whether to save audio to file
            
        Returns:
            Path to saved file if save_file=True, None otherwise
        """
        try:
            print("🎤 Starting text-to-speech conversion...")
            
            # Generate audio
            audio_data = self.generate_audio(
                text=text,
                voice_id=voice_id,
                bitrate=bitrate,
                speed=speed,
                pitch=pitch
            )
            
            if save_file:
                print("💾 Saving audio file...")
                # Save to file
                saved_path = self.save_audio(audio_data, output_filename)
                print(f"🎉 Audio generation complete! Saved to: {saved_path}")
                return saved_path
            else:
                return audio_data
                
        except Exception as e:
            print(f"❌ Audio generation failed: {str(e)}")
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
    """Command-line interface for UnrealSpeech TTS"""
    parser = argparse.ArgumentParser(description="UnrealSpeech Text-to-Speech Generator")
    parser.add_argument("--text", "-t", required=True, help="Text to convert to speech")
    parser.add_argument("--voice", "-v", default="Scarlett", help="Voice ID to use")
    parser.add_argument("--output", "-o", help="Output filename")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--bitrate", default="192k", help="Audio bitrate (128k, 192k, 256k, 320k)")
    parser.add_argument("--speed", type=float, default=0.0, help="Speech speed (-1.0 to 1.0)")
    parser.add_argument("--pitch", type=float, default=1.0, help="Speech pitch (0.5 to 2.0)")
    
    args = parser.parse_args()
    
    try:
        tts = UnrealSpeechTTS()
        
        if args.list_voices:
            tts.list_voices()
            return
        
        # Generate and save audio
        output_path = tts.text_to_speech(
            text=args.text,
            output_filename=args.output,
            voice_id=args.voice,
            bitrate=args.bitrate,
            speed=args.speed,
            pitch=args.pitch
        )
        
        print(f"Audio generated successfully: {output_path}")
        
    except Exception as e:
        logger.error(f"Command-line execution failed: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())