"""台語／華語語音轉寫引擎。

刻意把引擎抽成一層介面，理由有兩個：

1. 台語模型還沒定案。Breeze-ASR-26（Apache 2.0、輸出漢字）與台南大學的
   whisper-large-v3-turbo 台語版（CC BY-NC 4.0，不可商用）各有取捨，
   換引擎時只該動設定值，不該動 view 或前端。
2. 專案裡本來就有一套 sherpa-onnx SenseVoice（Live2D 角色對話在用），
   華語轉寫可以直接沿用，不必為它再載一份模型。

共同約定：輸入一律是 16kHz 單聲道 float32（-1.0 ~ 1.0），
由前端用 Web Audio 降頻後送上來——這樣伺服器端不需要 ffmpeg 解碼。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
from django.conf import settings

SAMPLE_RATE = 16000


@dataclass
class Transcript:
    text: str
    engine: str
    language: str = ""


class ASREngine:
    """轉寫引擎的共同介面。實作要自己保證 transcribe 是 thread-safe。"""

    name = "base"

    def transcribe(self, audio: np.ndarray) -> Transcript:  # pragma: no cover - 介面
        raise NotImplementedError


class FasterWhisperEngine(ASREngine):
    """CTranslate2 版的 Whisper（faster-whisper）。

    台語 fine-tune 的 Whisper 走這條。CPU 上務必用 int8：
    模型權重就算存成 float16，CTranslate2 也能在載入時量化。
    """

    name = "faster_whisper"

    def __init__(self, model_path: str, *, device: str = "cpu", compute_type: str = "int8",
                 language: str = "zh", beam_size: int = 1) -> None:
        from faster_whisper import WhisperModel

        self.language = language
        self.beam_size = beam_size
        # 模型只載一次；faster-whisper 的 transcribe 本身不保證併發安全，
        # 因此外面用鎖串起來（求籤是一次一句，不需要真的併發）。
        self._model = WhisperModel(model_path, device=device, compute_type=compute_type)
        self._lock = threading.Lock()

    def transcribe(self, audio: np.ndarray) -> Transcript:
        with self._lock:
            segments, info = self._model.transcribe(
                audio,
                language=self.language,
                task="transcribe",
                beam_size=self.beam_size,
                # 求籤是一句話，關掉前文條件避免它自己接故事
                condition_on_previous_text=False,
                vad_filter=True,
            )
            text = "".join(segment.text for segment in segments).strip()
        return Transcript(text=text, engine=self.name, language=getattr(info, "language", self.language) or "")


class SenseVoiceEngine(ASREngine):
    """沿用 Live2D 那套 sherpa-onnx SenseVoice（華語／粵語／日韓，不含台語）。"""

    name = "sense_voice"

    def __init__(self) -> None:
        # 跟 service_context.init_asr 同一套建構方式，設定值沿用角色設定，
        # 不另外開一份，避免兩邊的模型路徑各走各的。
        from apps.live2d.engine.asr.asr_factory import ASRFactory
        from apps.live2d.engine.character import build_config

        asr_config = build_config().character_config.asr_config
        self._impl = ASRFactory.get_asr_system(
            asr_config.asr_model,
            **getattr(asr_config, asr_config.asr_model).model_dump(),
        )
        self._lock = threading.Lock()

    def transcribe(self, audio: np.ndarray) -> Transcript:
        with self._lock:
            text = self._impl.transcribe_np(audio)
        return Transcript(text=(text or "").strip(), engine=self.name)


def to_wav_bytes(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """把 float32 樣本包成 16-bit PCM WAV。

    雲端 ASR 幾乎都吃 WAV，而 WAV 的標頭用標準庫 wave 就能寫，
    不需要 ffmpeg——這台機器上本來就沒有。
    """
    import io
    import wave

    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm16.tobytes())
    return buffer.getvalue()


class CloudASREngine(ASREngine):
    """通用的雲端轉寫引擎。

    刻意不綁定單一供應商：Hugging Face Inference（送 raw audio bytes）與
    OpenAI 相容的 /v1/audio/transcriptions（multipart）兩種請求形式都支援，
    換供應商只要改設定值。回傳格式兩邊都是 {"text": ...}，所以預設取 text。
    """

    name = "cloud"

    def __init__(self, url: str, *, token: str = "", mode: str = "raw", model: str = "",
                 language: str = "", timeout: float = 60.0) -> None:
        if not url:
            raise RuntimeError("ASR['CLOUD_URL'] 沒有設定。")
        self.url = url
        self.token = token
        self.mode = mode
        self.model = model
        self.language = language
        self.timeout = timeout

    def transcribe(self, audio: np.ndarray) -> Transcript:
        import httpx

        wav = to_wav_bytes(audio)
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        if self.mode == "multipart":
            files = {"file": ("audio.wav", wav, "audio/wav")}
            data = {}
            if self.model:
                data["model"] = self.model
            if self.language:
                data["language"] = self.language
            response = httpx.post(self.url, headers=headers, files=files, data=data, timeout=self.timeout)
        else:
            headers["Content-Type"] = "audio/wav"
            response = httpx.post(self.url, headers=headers, content=wav, timeout=self.timeout)

        response.raise_for_status()
        payload = response.json()
        # HF 與 OpenAI 相容端點都回 {"text": ...}；有些供應商會包一層 list
        if isinstance(payload, list) and payload:
            payload = payload[0]
        text = (payload or {}).get("text", "") if isinstance(payload, dict) else ""
        return Transcript(text=str(text).strip(), engine=self.name, language=self.language)


_engine: ASREngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> ASREngine:
    """取得（並在第一次呼叫時載入）設定指定的引擎。

    模型載入要好幾秒又吃記憶體，所以做成 process 內單例、用到才載，
    不要在 Django 啟動時就佔住——沒人用語音的時候不該付這個成本。
    """
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine

        config = getattr(settings, "ASR", {}) or {}
        kind = config.get("ENGINE", "faster_whisper")

        if kind == "faster_whisper":
            model_path = config.get("MODEL_PATH")
            if not model_path:
                raise RuntimeError(
                    "ASR['MODEL_PATH'] 沒有設定：faster-whisper 需要指向已轉成 "
                    "CTranslate2 格式的模型目錄。"
                )
            _engine = FasterWhisperEngine(
                model_path,
                device=config.get("DEVICE", "cpu"),
                compute_type=config.get("COMPUTE_TYPE", "int8"),
                language=config.get("LANGUAGE", "zh"),
                beam_size=int(config.get("BEAM_SIZE", 1)),
            )
        elif kind == "cloud":
            _engine = CloudASREngine(
                config.get("CLOUD_URL", ""),
                token=config.get("CLOUD_TOKEN", ""),
                mode=config.get("CLOUD_MODE", "raw"),
                model=config.get("CLOUD_MODEL", ""),
                language=config.get("LANGUAGE", ""),
                timeout=float(config.get("CLOUD_TIMEOUT", 60)),
            )
        elif kind == "sense_voice":
            _engine = SenseVoiceEngine()
        else:
            raise RuntimeError(f"未知的 ASR 引擎：{kind!r}")

        return _engine


def reset_engine() -> None:
    """測試用：把已載入的引擎丟掉，下次再載。"""
    global _engine
    with _engine_lock:
        _engine = None
