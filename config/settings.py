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
# `daphne -b 0.0.0.0 -p 8000`，不受這裡影響。daphne 因為排在 INSTALLED_APPS
# 最前面，它的 runserver 指令會蓋掉 Django 內建的那個，所以要動就直接改 daphne
# 這個 Command class 的 default_port，而不是去改 Django 內建那個。
from daphne.management.commands.runserver import Command as _DaphneRunserverCommand

_DaphneRunserverCommand.default_port = os.getenv("DJANGO_RUNSERVER_DEFAULT_PORT", "8003")

# 單一 process（單一容器/replica）時 InMemoryChannelLayer 就夠用，同一 process
# 內可以同時撐住很多個 WebSocket 連線。只有當要跑「多個」process/replica 分攤流
# 量或做高可用時，才需要讓 channel layer 跨 process 共享狀態——設定 REDIS_URL
# 就會自動切換成 channels_redis，不設就維持原本的單機行為。
REDIS_URL = os.getenv("REDIS_URL", "")
CHANNEL_LAYERS = {
    "default": (
        {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
        if REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    ),
}

# 多用戶同時寫入時，SQLite 預設的 rollback journal 模式一次只能有一個讀者或寫者持
# 有鎖，且「先取讀鎖、真正寫入時才升級成寫鎖」的預設行為容易在多個 request 同時
# 升級鎖時互撞成 `database is locked`。這裡改用 WAL（讀寫可並行）並讓
# transaction.atomic() 一開始就直接拿寫鎖（BEGIN IMMEDIATE），把「升級鎖衝突」
# 改成「排隊等鎖」，busy_timeout 內都會自動重試而不是立刻报錯。純資料庫連線層設
# 定，不影響任何 API 行為或流程。
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "ai_fortune.sqlite3",
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA busy_timeout=20000;"
                "PRAGMA cache_size=-20000;"
                "PRAGMA temp_store=MEMORY;"
            ),
        },
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

# nginx（或任何反向代理）終止 TLS 後，是用這個 header 告訴 Django 原始請求其實是
# https，不然 Django 會以為所有請求都是 http，連帶 SECURE_SSL_REDIRECT 和
# request.is_secure() 都會誤判。
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # http→https 的重新導向交給前面的 nginx 做就好，這裡預設關閉避免重複導向；
    # 如果反向代理不是本專案的 nginx、沒做這件事，再用環境變數打開。
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "False") == "True"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

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
