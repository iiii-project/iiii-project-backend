import abc
import asyncio
import os

from loguru import logger

from ..paths import RUNTIME_CACHE_DIR


class TTSInterface(metaclass=abc.ABCMeta):
    async def async_generate_audio(self, text: str, file_name_no_ext=None) -> str:
        return await asyncio.to_thread(self.generate_audio, text, file_name_no_ext)

    @abc.abstractmethod
    def generate_audio(self, text: str, file_name_no_ext=None) -> str:
        raise NotImplementedError

    def remove_file(self, filepath: str, verbose: bool = True) -> None:
        if not os.path.exists(filepath):
            logger.warning(f"File {filepath} does not exist")
            return
        try:
            logger.debug(f"Removing file {filepath}") if verbose else None
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Failed to remove file {filepath}: {e}")

    def generate_cache_file_name(self, file_name_no_ext=None, file_extension="wav"):
        cache_dir = RUNTIME_CACHE_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)

        if file_name_no_ext is None:
            file_name_no_ext = "temp"

        return str(cache_dir / f"{file_name_no_ext}.{file_extension}")
