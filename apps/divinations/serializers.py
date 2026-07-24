from rest_framework import serializers

from apps.fortunes.models import FortuneSet
from apps.fortunes.serializers import FortuneSerializer, FortuneSetSerializer

from .models import BlockCast, DivinationSession


class DivinationCreateSerializer(serializers.Serializer):
    fortune_set_code = serializers.CharField(max_length=50, default="SIXTY_JIAZI")
    question = serializers.CharField(min_length=2, max_length=300)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=DivinationSession.CATEGORY_CHOICES),
        required=True,
        allow_empty=False,
    )
    interaction_mode = serializers.ChoiceField(choices=DivinationSession.INTERACTION_CHOICES)
    anonymous_user_id = serializers.CharField(max_length=100, allow_blank=True, required=False, default="")
    fortune_number = serializers.IntegerField(min_value=1, required=False)

    def validate_fortune_set_code(self, value):
        if not FortuneSet.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError("找不到可用籤系")
        return value

    def validate(self, attrs):
        if "category" in self.initial_data:
            raise serializers.ValidationError({"category": "請改用 categories。"})
        attrs["categories"] = list(dict.fromkeys(attrs["categories"]))
        attrs["category"] = attrs["categories"][0]
        return attrs


class DivinationSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.CharField(source="session_uuid", read_only=True)
    user = serializers.IntegerField(source="user_id", read_only=True)
    fortune_set = FortuneSetSerializer(read_only=True)
    fortune = FortuneSerializer(read_only=True)
    interpretation = serializers.SerializerMethodField()

    class Meta:
        model = DivinationSession
        fields = [
            "session_id",
            "user",
            "anonymous_user_id",
            "fortune_set",
            "fortune",
            "question",
            "categories",
            "interaction_mode",
            "status",
            "confirmed",
            "interpretation",
            "ai_interpretation",
            "created_at",
            "updated_at",
            "completed_at",
        ]

    def get_interpretation(self, obj):
        if not obj.ai_interpretation:
            return None
        return {
            "overall_meaning": obj.ai_interpretation,
            "relation_to_question": "",
            "suggested_actions": [],
            "warnings": ["本系統僅供文化體驗及參考。"],
        }


class InterpretRequestSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=2, max_length=300, required=False)
    categories = serializers.ListField(
        child=serializers.ChoiceField(choices=DivinationSession.CATEGORY_CHOICES),
        required=False,
        allow_empty=False,
    )
    divination_result = serializers.DictField(required=False)

    def validate(self, attrs):
        if "category" in self.initial_data:
            raise serializers.ValidationError({"category": "請改用 categories。"})
        categories = attrs.get("categories")
        if categories:
            attrs["categories"] = list(dict.fromkeys(categories))
            attrs["category"] = attrs["categories"][0]

        return attrs


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
        if obj.result == "sheng":
            return 0
        return max(0, 3 - obj.attempt_number)


class ChatSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=500)
