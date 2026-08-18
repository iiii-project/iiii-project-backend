from pathlib import Path
import os

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is not True."
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "corsheaders",
    "django_filters",
    "rest_framework",
    "apps.accounts",
    "apps.fortunes",
    "apps.divinations",
    "apps.ai_service",
    "apps.system",
    "apps.live2d",
    "apps.speech",
]

# ── 語音轉寫 ──
# ENGINE:
#   "cloud"          線上 API（台語走這條）。CLOUD_URL 指到供應商端點：
#                    - Hugging Face Inference 跑 Breeze-ASR-26 → CLOUD_MODE=raw
#                    - OpenAI 相容的 /v1/audio/transcriptions → CLOUD_MODE=multipart
#   "faster_whisper" 本機跑台語 fine-tune 的 Whisper，需 MODEL_PATH 指向 CTranslate2 目錄
#   "sense_voice"    沿用 Live2D 那套 sherpa-onnx（華語可用、不含台語）
# 設定不全時語音端點會回 503 並請使用者打字——打字永遠是可用的路。
ASR = {
    "ENGINE": os.getenv("ASR_ENGINE", "cloud"),
    "LANGUAGE": os.getenv("ASR_LANGUAGE", "zh"),
    # 線上 API
    "CLOUD_URL": os.getenv("ASR_CLOUD_URL", ""),
    "CLOUD_TOKEN": os.getenv("ASR_CLOUD_TOKEN", ""),
    "CLOUD_MODE": os.getenv("ASR_CLOUD_MODE", "raw"),
    "CLOUD_MODEL": os.getenv("ASR_CLOUD_MODEL", ""),
    "CLOUD_TIMEOUT": os.getenv("ASR_CLOUD_TIMEOUT", "60"),
    # 本機模型
    "MODEL_PATH": os.getenv("ASR_MODEL_PATH", ""),
    "DEVICE": os.getenv("ASR_DEVICE", "cpu"),
    "COMPUTE_TYPE": os.getenv("ASR_COMPUTE_TYPE", "int8"),
    "BEAM_SIZE": os.getenv("ASR_BEAM_SIZE", "1"),
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# `manage.py runserver`（本機開發用）預設改成 8003，跟前端／其他專案常用的 8000
# 分開，避免本機同時開好幾個服務時互撞埠號。只影響本機 `uv run python manage.py
# runserver` 這種沒帶埠號的呼叫；Docker/正式環境走的是 Dockerfile 裡
# `gunicorn --bind 0.0.0.0:8000`，不受這裡影響。daphne 因為排在 INSTALLED_APPS
# 最前面，它的 runserver 指令會蓋掉 Django 內建的那個，所以要動就直接改 daphne
# 這個 Command class 的 default_port，而不是去改 Django 內建那個。
from daphne.management.commands.runserver import Command as _DaphneRunserverCommand

_DaphneRunserverCommand.default_port = os.getenv("DJANGO_RUNSERVER_DEFAULT_PORT", "8003")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "ai_fortune.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "EXCEPTION_HANDLER": "config.utils.api_exception_handler",
}

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "local-model")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
# 抽籤完成就在背景先跑解籤，讓使用者擲筊、看過場的時間拿來等 LLM（見 ai_service.services）
INTERPRET_PREWARM_ENABLED = os.getenv("INTERPRET_PREWARM_ENABLED", "True") == "True"
OPIK_ENABLED = os.getenv("OPIK_ENABLED", "True") == "True"
OPIK_PROJECT_NAME = os.getenv("OPIK_PROJECT_NAME", "ai-fortune")
