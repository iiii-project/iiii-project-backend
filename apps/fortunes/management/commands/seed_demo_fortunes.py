from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fortunes.models import Fortune, FortuneSet


class Command(BaseCommand):
    help = "Seed demo fortunes so the local divination flow can run."

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
        if fortune_set.fortunes.exists():
            self.stdout.write(self.style.WARNING("Fortunes already exist; skipped."))
            return

        Fortune.objects.bulk_create(
            [
                Fortune(
                    fortune_set=fortune_set,
                    number=number,
                    title=f"示範第{number}籤",
                    ganzhi="示範",
                    fortune_level="參考",
                    poem=f"這是第{number}支示範籤詩，用於本機開發流程測試。",
                    translation="此資料僅供開發測試，不代表正式六十甲子籤內容。",
                    story="示範資料尚未匯入正式典故。",
                    general_meaning="保持穩定，先釐清問題，再做下一步。",
                    career_meaning="工作上先確認資訊與風險，不急著做重大決定。",
                    love_meaning="關係中適合坦誠溝通，避免單方面猜測。",
                    study_meaning="學習上宜建立節奏，逐步補齊基礎。",
                    wealth_meaning="財務上先保守規劃，避免衝動投入。",
                    health_meaning="健康問題請以專業醫療意見為準。",
                    family_meaning="家庭溝通宜放慢語氣，先聽清楚彼此需求。",
                    relationship_meaning="人際互動中適合降低誤會，保留彈性。",
                    travel_meaning="出行前先確認時間、交通與安全安排。",
                    source_reference="demo seed; replace with official source data",
                )
                for number in range(1, 61)
            ]
        )
        self.stdout.write(self.style.SUCCESS("Created 60 demo fortunes."))
