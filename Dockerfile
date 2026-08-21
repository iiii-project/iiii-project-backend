FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# curl/bzip2:docker-entrypoint.sh 用來在容器啟動時自動下載/解壓 Live2D 角色的
# SenseVoice ASR 模型(~1.1GB,故意不進 git/image,第一次啟動時才抓進 volume)。
RUN apt-get update && apt-get install -y --no-install-recommends curl bzip2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev
RUN python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
