from typing import Type

from .tts_interface import TTSInterface


class TTSFactory:
    @staticmethod
    def get_tts_engine(engine_type: str, **kwargs) -> Type[TTSInterface]:
        if engine_type == "edge_tts":
            from .edge_tts import TTSEngine as EdgeTTSEngine

            return EdgeTTSEngine(
                voice=kwargs.get("voice"),
                rate=kwargs.get("rate", "+0%"),
                pitch=kwargs.get("pitch", "+0Hz"),
            )

        raise ValueError(f"Unknown TTS engine: {engine_type}")
