import asyncio
import base64

from pydub import AudioSegment
from pydub.utils import make_chunks

from ..agent.output_types import Actions, DisplayText


def _get_volume_by_chunks(audio: AudioSegment, chunk_length_ms: int) -> list:
    """Normalized RMS volume per chunk, used by the frontend for lip-sync."""
    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]


def _prepare_audio_payload_sync(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
) -> dict:
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()

    if not audio_path:
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions.to_dict() if actions else None,
        }

    try:
        audio = AudioSegment.from_file(audio_path)
        audio_bytes = audio.export(format="wav").read()
    except Exception as e:
        raise ValueError(f"Error loading or converting generated audio file to wav file '{audio_path}': {e}")

    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    volumes = _get_volume_by_chunks(audio, chunk_length_ms)

    return {
        "type": "audio",
        "audio": audio_base64,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions.to_dict() if actions else None,
    }


async def prepare_audio_payload(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
) -> dict:
    """Async wrapper: pydub/ffmpeg decoding is blocking, run it off the event loop."""
    return await asyncio.to_thread(
        _prepare_audio_payload_sync,
        audio_path,
        chunk_length_ms,
        display_text,
        actions,
    )
