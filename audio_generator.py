"""
Audio Generator - Integration between OpenAI and ElevenLabs
Combines OpenAI text generation with ElevenLabs audio synthesis
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from unrealspeech_tts import UnrealSpeechTTS
from openAI import OpenAIClient
from config import *

logger = logging.getLogger(__name__)

class AudioGenerator:
    """Integrated audio generator using OpenAI and ElevenLabs"""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        unrealspeech_api_key: Optional[str] = None
    ):
        """
        Initialize Audio Generator with both APIs
        
        Args:
            openai_api_key: OpenAI API key
            unrealspeech_api_key: UnrealSpeech API key
        """
        self.openai_client = OpenAIClient(api_key=openai_api_key)
        self.tts_client = UnrealSpeechTTS(api_key=unrealspeech_api_key)
        
        logger.info("Audio Generator initialized with OpenAI and UnrealSpeech clients")
    
    def generate_text_and_audio(
        self,
        prompt: str,
        voice_id: str = DEFAULT_VOICE_ID,
        voice_settings: Optional[Dict[str, Any]] = None,
        output_filename: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        save_text: bool = True
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
            save_text: Whether to save the text files
            
        Returns:
            Dictionary containing generated text and audio file path
        """
        try:
            print("\n🚀 Starting AI Audio Generation Process...")
            print(f"📝 Prompt: {prompt[:100]}...")
            
            logger.info("Starting text generation with OpenAI")
            print("🤖 Generating text with OpenAI...")
            
            # Generate text using OpenAI
            generated_text = self.openai_client.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            if not generated_text:
                raise ValueError("OpenAI generated empty or invalid text")
            
            print(f"✅ Text generated successfully ({len(generated_text)} characters)")
            logger.info(f"Generated text ({len(generated_text)} characters)")
            logger.debug(f"Text preview: {generated_text[:100]}...")
            
            # Save text files if requested
            text_file_path = None
            if save_text:
                text_file_path = self._save_text_files(prompt, generated_text)
            
            # Convert text to audio using UnrealSpeech
            print("🎵 Converting text to audio with UnrealSpeech...")
            logger.info("Converting text to audio with UnrealSpeech")
            
            audio_path = self.tts_client.text_to_speech(
                text=generated_text,
                output_filename=output_filename,
                voice_id=voice_id
            )
            
            result = {
                "text": generated_text,
                "audio_path": audio_path,
                "text_file_path": text_file_path,
                "prompt": prompt,
                "voice_id": voice_id
            }
            
            print("🎉 Audio generation completed successfully!")
            logger.info("Text-to-audio generation completed successfully")
            return result
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
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
    
    def _save_text_files(self, prompt: str, generated_text: str) -> Path:
        """Save the prompt and generated text to files"""
        import time
        timestamp = int(time.time())
        
        # Create text output directory
        text_dir = Path("generated_text")
        text_dir.mkdir(exist_ok=True)
        
        # Save both prompt and generated text
        text_filename = f"story_{timestamp}.txt"
        text_path = text_dir / text_filename
        
        print(f"💾 Saving text files to: {text_dir}")
        
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(f"=== PROMPT ===\n")
            f.write(f"{prompt}\n\n")
            f.write(f"=== GENERATED TEXT ===\n")
            f.write(f"{generated_text}\n\n")
            f.write(f"=== METADATA ===\n")
            f.write(f"Generated at: {time.ctime()}\n")
            f.write(f"Text length: {len(generated_text)} characters\n")
        
        print(f"✅ Text saved successfully: {text_path}")
        return text_path

def demo_workflow():
    """Demonstration of the complete workflow"""
    try:
        print("=" * 60)
        print("🎯 AI AUDIO GENERATOR DEMO")
        print("=" * 60)
        
        # Initialize audio generator
        print("🔧 Initializing AI Audio Generator...")
        generator = AudioGenerator()
        print("✅ Generator initialized successfully!")
        
        # Example prompt
        prompt = "Write a short story about a robot who discovers emotions for the first time."
        
        # Generate text and audio
        result = generator.generate_text_and_audio(
            prompt=prompt,
            voice_id=DEFAULT_VOICE_ID,
            max_tokens=500,
            temperature=0.8,
            save_text=True
        )
        
        print("\n" + "=" * 60)
        print("📊 GENERATION RESULTS")
        print("=" * 60)
        print(f"📝 Prompt: {result['prompt']}")
        print(f"📄 Generated Text Preview: {result['text'][:200]}...")
        print(f"🎵 Audio File: {result['audio_path']}")
        if 'text_file_path' in result:
            print(f"💾 Text File: {result['text_file_path']}")
        print(f"🎤 Voice Used: {result['voice_id']}")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        logger.error(f"Demo workflow failed: {str(e)}")
        print(f"❌ Demo failed: {str(e)}")
        return None

if __name__ == "__main__":
    # Run demonstration
    demo_workflow()
