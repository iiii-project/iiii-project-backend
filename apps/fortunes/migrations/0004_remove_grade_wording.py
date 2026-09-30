"""移除六十甲子籤「一般解釋」文字裡殘留的籤等字眼。

0003 已經拿掉 fortune_level 欄位，但有幾首的 general_meaning 內文本身還寫著
「偏向中下」「屬中平」「大吉之籤」，解籤時 LLM 會照著講出來。這裡只替換這幾段
確切的字句；管理端若已自行改過內文、找不到原句，就不動它。
籤詩原文與白話翻譯裡的「逢大吉」是古文本身，不在此列。
"""

from django.db import migrations

REPLACEMENTS = {
    40: ("值得放心期待的大吉之籤。", "值得放心期待的一支籤。"),
    55: ("這支籤偏向中下，提醒", "這支籤提醒"),
    57: ("這支籤偏向中吉，只要", "這支籤提示，只要"),
    60: ("這支籤屬中平，象徵", "這支籤象徵"),
}


def remove_grade_wording(apps, schema_editor):
    Fortune = apps.get_model("fortunes", "Fortune")
    for number, (old, new) in REPLACEMENTS.items():
        for fortune in Fortune.objects.filter(fortune_set__code="SIXTY_JIAZI", number=number):
            if old in fortune.general_meaning:
                fortune.general_meaning = fortune.general_meaning.replace(old, new)
                fortune.save(update_fields=["general_meaning"])


class Migration(migrations.Migration):
    dependencies = [
        ("fortunes", "0003_remove_fortune_level"),
    ]

    operations = [
        migrations.RunPython(remove_grade_wording, migrations.RunPython.noop),
    ]
