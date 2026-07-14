from django.db.models import Count
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.divinations.models import DivinationSession
from config.utils import ok


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(ok({"status": "ok"}))


class UsageStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        sessions = DivinationSession.objects.all()
        return Response(
            ok(
                {
                    "total_sessions": sessions.count(),
                    "completed_sessions": sessions.filter(status="completed").count(),
                    "by_status": list(sessions.values("status").annotate(count=Count("id")).order_by("status")),
                    "by_category": list(sessions.values("category").annotate(count=Count("id")).order_by("category")),
                }
            )
        )


class HomeContentView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            ok(
                {
                    "eyebrow": "TAIWAN TEMPLE ORACLE · 六十甲子籤",
                    "title": "AI 求籤互動系統",
                    "description": "以網頁互動、動作辨識與 AI 解說重現求籤流程，作為傳統文化展示、教育與娛樂參考。",
                    "steps": ["輸入問題", "燒香祈求", "搖籤", "擲筊確認", "AI 解籤"],
                    "notice": "攝影機影像只在瀏覽器內處理，不會上傳後端。系統不宣稱預測未來，AI 回答僅供文化體驗及參考。",
                }
            )
        )
