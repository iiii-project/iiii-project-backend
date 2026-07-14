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
