#!/bin/sh
# 容器啟動流程：跑遷移 -> (可選)建立管理員 -> 用 daphne 起 ASGI app。
#
# 一定要用 ASGI(daphne)而不是 WSGI(gunicorn)起——/client-ws 的 Live2D
# 角色語音對話走的是 Django Channels 的 WebSocket,WSGI 完全無法處理這條路。
set -e

# Live2D 角色的語音辨識(ASR)模型故意不進 git/image(~1.1GB),第一次啟動、
# volume 裡還沒有時才下載——之後重啟/重新部署都會沿用 volume 裡已經下好的,不
# 會每次都重抓。下載失敗不擋啟動,apps/live2d/engine/service_context.py 的
# init_asr 會優雅降級成只能用文字聊天,不會讓角色整個顯示不出來。
SENSE_VOICE_DIR="/app/data/live2d/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
if [ ! -f "$SENSE_VOICE_DIR/model.int8.onnx" ]; then
    echo "SenseVoice ASR model not found, downloading (~1.1GB, one-time)..."
    mkdir -p /app/data/live2d/models
    set +e
    curl -fL --retry 3 -o /tmp/sense-voice.tar.bz2 \
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2"
    dl_ok=$?
    tar_ok=1
    if [ "$dl_ok" -eq 0 ]; then
        tar xf /tmp/sense-voice.tar.bz2 -C /app/data/live2d/models
        tar_ok=$?
    fi
    set -e
    rm -f /tmp/sense-voice.tar.bz2
    if [ "$dl_ok" -eq 0 ] && [ "$tar_ok" -eq 0 ]; then
        echo "SenseVoice ASR model ready."
    else
        echo "WARNING: failed to download/extract SenseVoice ASR model, voice input will be unavailable until this succeeds on a later restart."
    fi
fi

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
