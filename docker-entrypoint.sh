#!/bin/sh
# 容器啟動流程：跑遷移 -> (可選)建立管理員 -> 用 daphne 起 ASGI app。
#
# 一定要用 ASGI(daphne)而不是 WSGI(gunicorn)起——/client-ws 的 Live2D
# 角色語音對話走的是 Django Channels 的 WebSocket,WSGI 完全無法處理這條路。
set -e

python manage.py migrate --noinput

# 預設不自動建立管理員帳號,避免密碼用環境變數預設值就悄悄建出一個帳號。要建的
# 話明確設 DJANGO_CREATE_SUPERUSER=true,並確保 DJANGO_SUPERUSER_PASSWORD 是你
# 自己設定的強密碼,不要用 .env.example 裡的範例值。
if [ "${DJANGO_CREATE_SUPERUSER:-false}" = "true" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
password = os.environ['DJANGO_SUPERUSER_PASSWORD']
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'created superuser: {username}')
else:
    print(f'superuser already exists, skipping: {username}')
"
fi

exec daphne -b 0.0.0.0 -p 8000 --access-log - config.asgi:application
