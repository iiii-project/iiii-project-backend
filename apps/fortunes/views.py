from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from config.utils import ok

from .models import Fortune, FortuneSet
from .serializers import FortuneSerializer, FortuneSetSerializer


class FortuneSetListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        sets = FortuneSet.objects.filter(is_active=True, is_public=True).order_by("-is_default", "name")
        return Response(ok({"items": FortuneSetSerializer(sets, many=True).data}))


class FortuneDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, fortune_set_code, number):
        fortune = get_object_or_404(
            Fortune.objects.select_related("fortune_set"),
            fortune_set__code=fortune_set_code,
            fortune_set__is_active=True,
            fortune_set__is_public=True,
            number=number,
            is_active=True,
        )
        return Response(ok(FortuneSerializer(fortune).data))
