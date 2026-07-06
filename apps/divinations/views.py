from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_service.services import chat_about_session, interpret_session
from config.utils import ok

from .models import DivinationSession
from .serializers import BlockCastSerializer, ChatSerializer, DivinationCreateSerializer, DivinationSessionSerializer
from .services import cast_blocks, complete_prayer, create_session, draw_fortune


class DivinationListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        anonymous_user_id = request.query_params.get("anonymous_user_id", "")
        sessions = DivinationSession.objects.select_related("fortune_set", "fortune").order_by("-created_at")
        if anonymous_user_id:
            sessions = sessions.filter(anonymous_user_id=anonymous_user_id)
        return Response(ok({"items": DivinationSessionSerializer(sessions[:50], many=True).data}))

    def post(self, request):
        serializer = DivinationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = create_session(**serializer.validated_data)
        return Response(ok(DivinationSessionSerializer(session).data), status=201)


class DivinationDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get_object(self, session_id):
        return get_object_or_404(
            DivinationSession.objects.select_related("fortune_set", "fortune"), session_uuid=session_id
        )

    def get(self, request, session_id):
        return Response(ok(DivinationSessionSerializer(self.get_object(session_id)).data))

    def delete(self, request, session_id):
        self.get_object(session_id).delete()
        return Response(ok(message="已刪除"))


class PrayerCompleteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, session_id):
        session = complete_prayer(session_id)
        return Response(ok(DivinationSessionSerializer(session).data))


class DrawFortuneView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, session_id):
        session = draw_fortune(session_id)
        return Response(ok(DivinationSessionSerializer(session).data))


class BlockCastView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, session_id):
        cast = cast_blocks(session_id)
        return Response(ok(BlockCastSerializer(cast).data))


class InterpretView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, session_id):
        session = interpret_session(session_id)
        return Response(ok(DivinationSessionSerializer(session).data))


class ChatView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, session_id):
        serializer = ChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = chat_about_session(session_id, serializer.validated_data["message"])
        return Response(ok({"reply": reply, "remaining_messages": None}))
