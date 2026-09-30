"""籤等已從資料模型移除；籤書內文也不應再出現籤等字眼。"""

import importlib
import json
import re
from pathlib import Path

from django.apps import apps

from apps.fortunes.models import Fortune, FortuneSet

DATA_FILE = Path(__file__).resolve().parent.parent / "apps" / "fortunes" / "data" / "sixty_jiazi_data.json"
# 籤等的寫法：「上上籤」「中下籤」「偏向中吉」「屬中平」「大吉之籤」等。
# 不能單比對「中平」兩個字，否則「家中平安」也會被誤判。
GRADE_RE = re.compile(r"(上上|上吉|中吉|中平|中下|下下)籤|(偏向|屬)(上上|上吉|中吉|中平|中下|下下)|大吉之籤")
# 籤詩原文與其白話翻譯裡的「逢大吉」是古文本身，不算籤等標示
MEANING_FIELDS = [
    "general_meaning", "love_meaning", "career_meaning", "study_meaning", "wealth_meaning",
    "health_meaning", "family_meaning", "relationship_meaning", "travel_meaning", "story",
]


def test_seed_data_has_no_grade_wording():
    for entry in json.loads(DATA_FILE.read_text(encoding="utf-8")):
        for field in MEANING_FIELDS:
            assert not GRADE_RE.search(entry.get(field, "")), (entry["number"], field)


def test_migration_rewrites_existing_rows(db):
    migration = importlib.import_module("apps.fortunes.migrations.0004_remove_grade_wording")
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    old_text = "這支籤偏向中下，提醒現階段進退兩難、時機未到。"
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=55, poem="詩", general_meaning=old_text)
    edited = Fortune.objects.create(fortune_set=fortune_set, number=57, poem="詩", general_meaning="管理端改過的內容")

    migration.remove_grade_wording(apps, None)

    fortune.refresh_from_db()
    edited.refresh_from_db()
    assert fortune.general_meaning == "這支籤提醒現階段進退兩難、時機未到。"
    assert edited.general_meaning == "管理端改過的內容"
