"""語音轉寫端點。

前端送上來的是 16kHz 單聲道 float32 的原始樣本（Web Audio 抓的、已在瀏覽器降頻），
所以伺服器端不需要 ffmpeg，也不必猜 webm/opus 或 mp4/aac 的容器格式。
"""

from __future__ import annotations

import numpy as np
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from config.utils import fail, ok

from .engines import SAMPLE_RATE, get_engine

# 求籤的心事就一兩句話，給到 60 秒已經很寬鬆；
# 設上限主要是擋掉誤傳整首歌把 CPU 佔死。
MAX_SECONDS = 60
MAX_BYTES = SAMPLE_RATE * 4 * MAX_SECONDS  # float32 = 4 bytes
MIN_SECONDS = 0.3


class TranscribeView(APIView):
    """POST /api/v1/speech/transcribe/

    multipart/form-data，欄位 `audio`：16kHz 單聲道 float32 little-endian 原始樣本。
    """

    parser_classes = [MultiPartParser]
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        upload = request.FILES.get("audio")
        if upload is None:
            return Response(fail("AUDIO_REQUIRED", "沒有收到語音資料。"), status=400)

        if upload.size > MAX_BYTES:
            return Response(
                fail("AUDIO_TOO_LONG", f"語音太長了，請講在 {MAX_SECONDS} 秒內。"),
                status=413,
            )

        raw = upload.read()
        if len(raw) % 4:
            return Response(fail("AUDIO_MALFORMED", "語音資料格式不正確。"), status=400)

        audio = np.frombuffer(raw, dtype="<f4")
        if audio.size < SAMPLE_RATE * MIN_SECONDS:
            return Response(fail("AUDIO_TOO_SHORT", "太短了，請按住多說一點。"), status=400)

        # float32 可能夾帶 NaN／inf（某些瀏覽器在裝置切換時會吐出來），
        # 直接餵給模型會整段變成靜音或炸掉，先清乾淨。
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak < 1e-4:
            return Response(fail("AUDIO_SILENT", "沒有聽到聲音，請確認麥克風。"), status=400)

        try:
            engine = get_engine()
        except Exception as exc:  # 模型沒放好／設定沒填，屬於部署問題
            return Response(
                fail("ASR_UNAVAILABLE", "語音辨識目前無法使用，請直接打字。", str(exc)),
                status=503,
            )

        try:
            result = engine.transcribe(audio)
        except Exception as exc:
            return Response(
                fail("ASR_FAILED", "語音辨識失敗了，請再試一次或直接打字。", str(exc)),
                status=500,
            )

        return Response(
            ok(
                {
                    "text": result.text,
                    "engine": result.engine,
                    "language": result.language,
                    "duration": round(audio.size / SAMPLE_RATE, 2),
                }
            )
        )
