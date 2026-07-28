# AI Fortune Backend

Minimal Django backend for the AI 求籤互動系統.

## Setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

`migrate` seeds the full 六十甲子籤 content automatically via a data migration, so no extra step is needed. To re-apply the seed data after editing `apps/fortunes/data/sixty_jiazi_data.json` on a database that already ran this migration, run `uv run python manage.py seed_demo_fortunes`.

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
CSRF_TRUSTED_ORIGINS=http://localhost:5173
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=
LLM_MODEL=local-model
LLM_TIMEOUT_SECONDS=20
```

## Checks

```bash
uv run pytest
```

## Docker Compose

Docker Compose starts both Django and llama.cpp. Docker must run Linux `x86_64` containers and have Compose v2 installed.

### Before Starting

1. Ensure `llamacpp/llamacpp-linux/` contains the complete Linux llama.cpp release, including `llama-server` and the `*.so.0.0.9873` files. Do not copy it through a tool that truncates binary files.
2. Put one or more GGUF models in `llamacpp/model/`.
3. Create the production environment file and set safe values:

```bash
cp .env.example .env
```

```text
DJANGO_SECRET_KEY=use-a-long-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.example
CORS_ALLOWED_ORIGINS=https://your-frontend.example
CSRF_TRUSTED_ORIGINS=https://your-frontend.example
DJANGO_SUPERUSER_PASSWORD=use-a-strong-password
LLAMA_MODEL=your-model.gguf
LLAMA_MODEL_ALIAS=local-model
```

Leave `LLAMA_MODEL` empty to select the first compatible GGUF model in sorted order. `LLAMA_MODEL` may also be its numbered position in that list.

4. Validate the Compose configuration:

```bash
docker compose config -q
```

### Start

```bash
docker compose up -d --build
```

On every start, the `web` service runs `python manage.py migrate --noinput` before Gunicorn. This creates `/app/data/ai_fortune.sqlite3` and all database tables in the `sqlite_data` Docker volume automatically, including the full 六十甲子籤 fortune data (seeded once via a data migration, so it only runs on first start and is safe to leave in the startup command on restarts).

Check the two services and their logs:

```bash
docker compose ps
docker compose logs -f llama
docker compose logs -f web
```

The API is available at `http://localhost:8000/api/v1/`; llama.cpp is available at `http://localhost:1234/v1/`. Verify both services:

```bash
curl http://localhost:1234/health
curl http://localhost:1234/v1/models
curl http://localhost:8000/api/v1/health/
```

SQLite data and uploads are stored in Docker volumes. The first start creates `admin` with password `1234`; override `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD` before production use. Set `DJANGO_PORT` or `LLAMA_HOST_PORT` to expose a different host port.

If llama.cpp was previously deployed from Windows, force its recreation after updating Compose; its startup command repairs CRLF and missing `.so` symbolic links:

```bash
docker compose up -d --build --force-recreate llama
```
