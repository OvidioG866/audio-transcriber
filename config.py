"""
Configuration settings for ElevenLabs TTS integration
"""
import os
from pathlib import Path

# API Configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ElevenLabs Settings
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
DEFAULT_MODEL_ID = "eleven_monolingual_v1"
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True
}

# Audio Settings
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
AUDIO_OUTPUT_DIR = Path("generated_audio")
SUPPORTED_FORMATS = ["mp3_44100_128", "mp3_22050_32", "pcm_16000", "pcm_22050", "pcm_24000", "pcm_44100"]

# Rate Limiting
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Logging Configuration
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# File Management
MAX_FILENAME_LENGTH = 50
AUDIO_FILE_PREFIX = "tts_audio"

# Ensure output directory exists
AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)
