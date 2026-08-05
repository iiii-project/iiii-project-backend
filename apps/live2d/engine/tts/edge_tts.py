import edge_tts
from loguru import logger

from .tts_interface import TTSInterface

# See https://github.com/rany2/edge-tts . Use `edge-tts --list-voices` to list voices.


class TTSEngine(TTSInterface):
    def __init__(self, voice="en-US-AvaMultilingualNeural", rate="+0%", pitch="+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.file_extension = "mp3"

    def generate_audio(self, text, file_name_no_ext=None):
        file_name = self.generate_cache_file_name(file_name_no_ext, self.file_extension)
        try:
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            communicate.save_sync(file_name)
        except Exception as e:
            logger.critical(f"edge-tts unable to generate audio: {e}")
            logger.critical("It's possible that edge-tts is blocked in your region.")
            return None
        return file_name
