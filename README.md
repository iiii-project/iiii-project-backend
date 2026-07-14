# AI Fortune Backend

Minimal Django backend for the AI 求籤互動系統.

## Setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

API base: `http://127.0.0.1:8000/api/v1/`

## API

完整端點、認證、請求與回應格式請見 [docs/API.md](docs/API.md)。

## Environment

Copy `.env.example` to `.env` for local overrides.

```text
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=
LLM_MODEL=local-model
LLM_TIMEOUT_SECONDS=20
```

## Checks

```bash
uv run pytest
```
