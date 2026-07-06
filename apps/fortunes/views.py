from rest_framework.views import APIView
from rest_framework.response import Response

from config.utils import ok

from .models import FortuneSet
from .serializers import FortuneSetSerializer


class FortuneSetListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        sets = FortuneSet.objects.filter(is_active=True, is_public=True).order_by("-is_default", "name")
        return Response(ok({"items": FortuneSetSerializer(sets, many=True).data}))
