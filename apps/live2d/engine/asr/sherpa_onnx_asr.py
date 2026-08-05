"""SenseVoice (sherpa-onnx) ASR provider.

Trimmed from upstream open_llm_vtuber: only the `sense_voice` model_type is kept
(the only one this character uses), and the auto-download-on-missing-model fallback
is dropped — deployment is expected to provide the model files under paths.MODEL_DIR.
"""

import os

import numpy as np
import onnxruntime
import sherpa_onnx
from loguru import logger
from opencc import OpenCC

from .asr_interface import ASRInterface


class VoiceRecognition(ASRInterface):
    def __init__(
        self,
        model_type: str = "sense_voice",
        sense_voice: str = None,
        tokens: str = None,
        num_threads: int = 1,
        use_itn: bool = True,
        debug: bool = False,
        convert_to_traditional_chinese: bool = False,
        provider: str = "cpu",
        language: str = "",
        **_ignored,
    ) -> None:
        if model_type != "sense_voice":
            raise ValueError(
                f"This trimmed ASR provider only supports model_type='sense_voice', got: {model_type!r}"
            )
        self.sense_voice = sense_voice
        self.tokens = tokens
        self.num_threads = num_threads
        self.use_itn = use_itn
        self.debug = debug
        self.language = language
        self.SAMPLE_RATE = 16000
        self.traditional_chinese_converter = OpenCC("s2twp") if convert_to_traditional_chinese else None

        self.provider = provider
        if self.provider == "cuda":
            try:
                if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
                    logger.warning("CUDA provider not available for ONNX. Falling back to CPU.")
                    self.provider = "cpu"
            except ImportError:
                logger.warning("ONNX Runtime not installed. Falling back to CPU.")
                self.provider = "cpu"
        logger.info(f"Sherpa-Onnx-ASR: Using {self.provider} for inference")

        if not self.sense_voice or not os.path.isfile(self.sense_voice):
            raise FileNotFoundError(
                f"SenseVoice model not found at {self.sense_voice!r}. Provide the model.onnx path."
            )

        self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=self.sense_voice,
            tokens=self.tokens,
            num_threads=self.num_threads,
            use_itn=self.use_itn,
            debug=self.debug,
            provider=self.provider,
            language=self.language,
        )

    def transcribe_np(self, audio: np.ndarray) -> str:
        stream = self.recognizer.create_stream()
        stream.accept_waveform(self.SAMPLE_RATE, audio)
        self.recognizer.decode_streams([stream])
        text = stream.result.text
        if self.traditional_chinese_converter:
            return self.traditional_chinese_converter.convert(text)
        return text
