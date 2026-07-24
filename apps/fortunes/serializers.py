from rest_framework import serializers

from .models import Fortune, FortuneSet


class FortuneSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = FortuneSet
        fields = ["code", "name", "description", "is_default"]


class FortuneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fortune
        fields = [
            "number",
            "title",
            "ganzhi",
            "fortune_level",
            "poem",
            "translation",
            "story",
            "general_meaning",
            "love_meaning",
            "career_meaning",
            "study_meaning",
            "wealth_meaning",
            "health_meaning",
            "family_meaning",
            "relationship_meaning",
            "travel_meaning",
        ]


class FortuneImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fortune
        fields = [
            "number",
            "title",
            "ganzhi",
            "fortune_level",
            "poem",
            "translation",
            "story",
            "general_meaning",
            "love_meaning",
            "career_meaning",
            "study_meaning",
            "wealth_meaning",
            "health_meaning",
            "family_meaning",
            "relationship_meaning",
            "travel_meaning",
            "source_reference",
            "is_active",
        ]


class FortuneBulkImportSerializer(serializers.Serializer):
    items = FortuneImportSerializer(many=True, allow_empty=False)
