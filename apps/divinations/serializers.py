from rest_framework import serializers

from apps.fortunes.models import FortuneSet
from apps.fortunes.serializers import FortuneSerializer, FortuneSetSerializer

from .models import BlockCast, DivinationSession


class DivinationCreateSerializer(serializers.Serializer):
    fortune_set_code = serializers.CharField(max_length=50, default="SIXTY_JIAZI")
    question = serializers.CharField(min_length=2, max_length=300)
    category = serializers.ChoiceField(choices=DivinationSession.CATEGORY_CHOICES)
    interaction_mode = serializers.ChoiceField(choices=DivinationSession.INTERACTION_CHOICES)
    anonymous_user_id = serializers.CharField(max_length=100, allow_blank=True, required=False, default="")

    def validate_fortune_set_code(self, value):
        if not FortuneSet.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("找不到可用籤系")
        return value


class DivinationSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(source="session_uuid", read_only=True)
    fortune_set = FortuneSetSerializer(read_only=True)
    fortune = FortuneSerializer(read_only=True)

    class Meta:
        model = DivinationSession
        fields = [
            "session_id",
            "anonymous_user_id",
            "fortune_set",
            "fortune",
            "question",
            "category",
            "interaction_mode",
            "status",
            "confirmed",
            "ai_interpretation",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class BlockCastSerializer(serializers.ModelSerializer):
    result_name = serializers.CharField(source="get_result_display", read_only=True)
    confirmed = serializers.BooleanField(source="divination_session.confirmed", read_only=True)
    remaining_attempts = serializers.SerializerMethodField()

    class Meta:
        model = BlockCast
        fields = [
            "attempt_number",
            "block_one",
            "block_two",
            "result",
            "result_name",
            "confirmed",
            "remaining_attempts",
        ]

    def get_remaining_attempts(self, obj):
        return max(0, 3 - obj.attempt_number)


class ChatSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=500)
