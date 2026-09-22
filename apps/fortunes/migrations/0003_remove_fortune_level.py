from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("fortunes", "0002_seed_sixty_jiazi_fortunes"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="fortune",
            name="fortune_level",
        ),
    ]
