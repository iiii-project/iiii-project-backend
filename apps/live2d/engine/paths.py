"""Data locations for the live2d engine, rooted under Django's data directory."""

from pathlib import Path

from django.conf import settings

DATA_DIR = Path(settings.BASE_DIR) / "data" / "live2d"
MODEL_DIR = DATA_DIR / "models"
RUNTIME_CACHE_DIR = DATA_DIR / "cache"
LIVE2D_MODELS_DIR = DATA_DIR / "live2d-models"
AVATARS_DIR = DATA_DIR / "avatars"
BACKGROUNDS_DIR = DATA_DIR / "backgrounds"
CHAT_HISTORY_DIR = DATA_DIR / "chat_history"

for _dir in (MODEL_DIR, RUNTIME_CACHE_DIR, LIVE2D_MODELS_DIR, AVATARS_DIR, BACKGROUNDS_DIR, CHAT_HISTORY_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
