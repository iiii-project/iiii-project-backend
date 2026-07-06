from rest_framework.response import Response
from rest_framework.views import APIView

from config.utils import ok


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(ok({"status": "ok"}))
