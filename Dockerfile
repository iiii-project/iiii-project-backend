FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py shell -c \"from django.contrib.auth import get_user_model; import os; User = get_user_model(); username = os.environ['DJANGO_SUPERUSER_USERNAME']; User.objects.filter(username=username).exists() or User.objects.create_superuser(username=username, email=os.environ['DJANGO_SUPERUSER_EMAIL'], password=os.environ['DJANGO_SUPERUSER_PASSWORD'])\" && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 120"]
