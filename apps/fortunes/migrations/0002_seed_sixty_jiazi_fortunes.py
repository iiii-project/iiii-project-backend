import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sixty_jiazi_data.json"


def seed_sixty_jiazi_fortunes(apps, schema_editor):
    FortuneSet = apps.get_model("fortunes", "FortuneSet")
    Fortune = apps.get_model("fortunes", "Fortune")

    fortune_set, _ = FortuneSet.objects.get_or_create(
        code="SIXTY_JIAZI",
        defaults={
            "name": "六十甲子籤",
            "description": "系統預設使用的籤系",
            "is_default": True,
            "is_public": True,
            "is_active": True,
        },
    )

    fortunes = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for entry in fortunes:
        Fortune.objects.update_or_create(
            fortune_set=fortune_set,
            number=entry["number"],
            defaults={
                "title": entry["title"],
                "ganzhi": entry["ganzhi"],
                "fortune_level": entry["fortune_level"],
                "poem": entry["poem"],
                "translation": entry["translation"],
                "story": entry["story"],
                "general_meaning": entry["general_meaning"],
                "love_meaning": entry["love_meaning"],
                "career_meaning": entry["career_meaning"],
                "study_meaning": entry["study_meaning"],
                "wealth_meaning": entry["wealth_meaning"],
                "health_meaning": entry["health_meaning"],
                "family_meaning": entry["family_meaning"],
                "relationship_meaning": entry["relationship_meaning"],
                "travel_meaning": entry["travel_meaning"],
                "source_reference": entry["source_reference"],
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("fortunes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_sixty_jiazi_fortunes, migrations.RunPython.noop),
    ]
