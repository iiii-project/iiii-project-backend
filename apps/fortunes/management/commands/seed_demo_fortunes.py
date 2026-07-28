import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fortunes.models import Fortune, FortuneSet

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sixty_jiazi_data.json"


class Command(BaseCommand):
    help = "Seed the official 六十甲子籤 fortunes so the divination flow can run."

    @transaction.atomic
    def handle(self, *args, **options):
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

        created_count = 0
        updated_count = 0
        for entry in fortunes:
            _, created = Fortune.objects.update_or_create(
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
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(fortunes)} 六十甲子籤 fortunes "
                f"({created_count} created, {updated_count} updated)."
            )
        )
