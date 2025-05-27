import os
import logging
from gtts import gTTS
from pydub import AudioSegment
import tempfile

logger = logging.getLogger(__name__)

class AudioGenerator:
    def __init__(self, output_dir="audio_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_audio(self, text, filename, language='en'):
        """
        Generate audio from text using gTTS
        
        Args:
            text (str): Text to convert to speech
            filename (str): Name of the output file (without extension)
            language (str): Language code for the text
            
        Returns:
            str: Path to the generated audio file
        """
        try:
            # Create a temporary file for the initial MP3
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name

            # Generate speech using gTTS
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(temp_path)

            # Load the audio file
            audio = AudioSegment.from_mp3(temp_path)

            # Add a small silence at the beginning and end
            silence = AudioSegment.silent(duration=500)  # 500ms silence
            audio = silence + audio + silence

            # Export the final audio file
            output_path = os.path.join(self.output_dir, f"{filename}.mp3")
            audio.export(output_path, format="mp3")

            # Clean up the temporary file
            os.unlink(temp_path)

            logger.info(f"Successfully generated audio file: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return None

    def generate_article_audio(self, article_data, filename_prefix="article"):
        """
        Generate audio for an article with its metadata
        
        Args:
            article_data (dict): Dictionary containing article data
            filename_prefix (str): Prefix for the output filename
            
        Returns:
            str: Path to the generated audio file
        """
        try:
            # Prepare the text with metadata
            text = f"Article: {article_data.get('headline', '')}\n\n"
            
            if article_data.get('author'):
                text += f"By {article_data['author']}\n"
            if article_data.get('date'):
                text += f"Published on {article_data['date']}\n\n"
                
            text += article_data.get('full_text', '')
            
            # Generate a unique filename
            filename = f"{filename_prefix}_{article_data.get('headline', '')[:30].replace(' ', '_')}"
            
            return self.generate_audio(text, filename)
            
        except Exception as e:
            logger.error(f"Error generating article audio: {str(e)}")
            return None 