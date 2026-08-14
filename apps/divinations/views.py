from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_service.services import (
    chat_about_session,
    interpret_session,
    list_session_messages,
    prewarm_interpretation,
    remaining_chat_messages,
)
from config.utils import ok

from .models import DivinationSession
from .serializers import (
    BlockCastSerializer,
    ChatSerializer,
    DivinationCreateSerializer,
    DivinationSessionSerializer,
    InterpretRequestSerializer,
)
from .services import cast_blocks, complete_prayer, create_session, draw_fortune


class DivinationListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        sessions = DivinationSession.objects.select_related("fortune_set", "fortune").order_by("-created_at")
        if request.user.is_authenticated:
            sessions = sessions.filter(user=request.user)
        else:
            anonymous_user_id = request.query_params.get("anonymous_user_id", "")
            if not anonymous_user_id:
                return Response(ok({"items": []}))
            sessions = sessions.filter(anonymous_user_id=anonymous_user_id)
        return Response(ok({"items": DivinationSessionSerializer(sessions[:50], many=True).data}))

    def post(self, request):
        serializer = DivinationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = create_session(
            **serializer.validated_data,
            user=request.user if request.user.is_authenticated else None,
        )
        # 查籤（帶 fortune_number 建立）一開始就把籤釘好、狀態直接是 confirmed，
        # 下一步一定是解籤，所以在這裡就先預熱，跟抽籤那條路一樣不必乾等。
        if session.fortune_id and session.confirmed:
            prewarm_interpretation(session)
        return Response(ok(DivinationSessionSerializer(session).data), status=201)


class DivinationDetailView(APIView):
    permission_classes = [AllowAny]

    def get_object(self, request, session_id):
        session = get_object_or_404(
            DivinationSession.objects.select_related("fortune_set", "fortune"), session_uuid=session_id
        )
        share_token = request.query_params.get("share")
        if share_token and str(session.share_token) == share_token:
            return session
        if session.user_id:
            if not request.user.is_authenticated:
                raise PermissionDenied("請登入後再查看此求籤紀錄")
            if session.user_id != request.user.id:
                raise NotFound("找不到這次求籤紀錄")
        return session

    def get(self, request, session_id):
        return Response(ok(DivinationSessionSerializer(self.get_object(request, session_id)).data))

    def delete(self, request, session_id):
        self.get_object(request, session_id).delete()
        return Response(ok(message="已刪除"))


class PrayerCompleteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        DivinationDetailView().get_object(request, session_id)
        session = complete_prayer(session_id)
        return Response(ok(DivinationSessionSerializer(session).data))


class DrawFortuneView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        DivinationDetailView().get_object(request, session_id)
        session = draw_fortune(session_id)
        # 籤一抽出來就開始生成解籤，等使用者擲完筊多半已經備好
        prewarm_interpretation(session)
        return Response(ok(DivinationSessionSerializer(session).data))
class BlockCastView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        DivinationDetailView().get_object(request, session_id)
        cast = cast_blocks(session_id)
        return Response(ok(BlockCastSerializer(cast).data))


class InterpretView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        DivinationDetailView().get_object(request, session_id)
        serializer = InterpretRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        session = interpret_session(session_id, serializer.validated_data)
        return Response(ok(DivinationSessionSerializer(session).data))


class ClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        with transaction.atomic():
            session = DivinationSession.objects.select_for_update().filter(session_uuid=session_id).first()
            if session is None or (session.user_id is not None and session.user_id != request.user.id):
                # Same body/status for "doesn't exist", "already someone else's",
                # and "not anonymous anymore" — session_id must not double as a
                # way to probe ownership of other people's records.
                raise NotFound("找不到這次求籤紀錄")
            if session.user_id != request.user.id:
                session.user = request.user
                session.anonymous_user_id = ""
                session.save(update_fields=["user", "anonymous_user_id", "updated_at"])
        return Response(ok(DivinationSessionSerializer(session).data))


class ChatView(APIView):
    def get_permissions(self):
        # Reading chat history requires the caller to be logged in as the owner
        # (STORY-003). Posting a new message keeps the site-wide anonymous-session
        # behavior, so only GET is locked down here.
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request, session_id):
        owns_session = DivinationSession.objects.filter(session_uuid=session_id, user=request.user).exists()
        if not owns_session:
            # Same status and body whether session_id belongs to someone else or
            # doesn't exist at all, so a non-owner request can't be used to probe
            # which session IDs are valid.
            raise NotFound("找不到這次求籤紀錄")
        return Response(
            ok({"messages": list_session_messages(session_id), "remaining_messages": remaining_chat_messages(session_id)})
        )

    def post(self, request, session_id):
        DivinationDetailView().get_object(request, session_id)
        serializer = ChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = chat_about_session(session_id, serializer.validated_data["message"])
        return Response(
            ok(
                {
                    "reply": result["reply"],
                    "messages": result["messages"],
                    "remaining_messages": result["remaining_messages"],
                }
            )
        )
