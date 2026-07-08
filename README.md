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

All application endpoints use the shared response envelope:

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

Errors use:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_SESSION_STATE",
    "message": "尚未取得聖筊，不能解籤",
    "details": null
  }
}
```

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/token/` | public | Issue JWT access and refresh tokens. |
| `POST` | `/api/v1/auth/token/refresh/` | public | Refresh JWT access token. |
| `GET` | `/api/v1/health/` | public | Health check. |
| `GET` | `/api/v1/fortune-sets/` | public | List active public fortune sets. |
| `GET` | `/api/v1/fortune-sets/{fortune_set_code}/fortunes/{number}/` | public | Get one active fortune. |
| `GET` | `/api/v1/divinations/?anonymous_user_id={id}` | public | List recent divination sessions, optionally filtered by anonymous user. |
| `POST` | `/api/v1/divinations/` | public | Create a divination session. Body: `fortune_set_code`, `question`, `category`, `interaction_mode`, optional `anonymous_user_id`, optional `fortune_number`. |
| `GET` | `/api/v1/divinations/{session_id}/` | public | Get session detail. |
| `DELETE` | `/api/v1/divinations/{session_id}/` | public | Delete one session and related records. |
| `POST` | `/api/v1/divinations/{session_id}/prayer-complete/` | public | Mark prayer step complete and advance flow. |
| `POST` | `/api/v1/divinations/{session_id}/draw/` | public | Draw a fortune; repeated calls return the original fortune. |
| `POST` | `/api/v1/divinations/{session_id}/blocks/` | public | Cast blocks once; max three attempts. |
| `POST` | `/api/v1/divinations/{session_id}/interpret/` | public | Generate or return AI interpretation. |
| `GET` | `/api/v1/divinations/{session_id}/chat/` | public | List chat messages after interpretation. |
| `POST` | `/api/v1/divinations/{session_id}/chat/` | public | Send follow-up chat message. Body: `message` up to 500 characters. |
| `GET` | `/api/v1/admin/usage-stats/` | admin JWT | Return session usage statistics. |

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
