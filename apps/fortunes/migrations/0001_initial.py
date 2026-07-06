from django.db import migrations, models
import django.db.models.deletion


def create_default_fortune_set(apps, schema_editor):
    FortuneSet = apps.get_model("fortunes", "FortuneSet")
    FortuneSet.objects.get_or_create(
        code="SIXTY_JIAZI",
        defaults={
            "name": "六十甲子籤",
            "description": "系統預設使用的籤系",
            "is_default": True,
            "is_public": True,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FortuneSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("source_name", models.CharField(blank=True, max_length=200)),
                ("version", models.CharField(blank=True, max_length=30)),
                ("prompt_template", models.TextField(blank=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_public", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Fortune",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("title", models.CharField(blank=True, max_length=100)),
                ("ganzhi", models.CharField(blank=True, max_length=20)),
                ("fortune_level", models.CharField(blank=True, max_length=30)),
                ("poem", models.TextField()),
                ("translation", models.TextField(blank=True)),
                ("story", models.TextField(blank=True)),
                ("general_meaning", models.TextField(blank=True)),
                ("love_meaning", models.TextField(blank=True)),
                ("career_meaning", models.TextField(blank=True)),
                ("study_meaning", models.TextField(blank=True)),
                ("wealth_meaning", models.TextField(blank=True)),
                ("health_meaning", models.TextField(blank=True)),
                ("family_meaning", models.TextField(blank=True)),
                ("relationship_meaning", models.TextField(blank=True)),
                ("travel_meaning", models.TextField(blank=True)),
                ("source_reference", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "fortune_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fortunes",
                        to="fortunes.fortuneset",
                    ),
                ),
            ],
            options={"ordering": ["fortune_set", "number"]},
        ),
        migrations.AddConstraint(
            model_name="fortune",
            constraint=models.UniqueConstraint(
                fields=("fortune_set", "number"), name="unique_fortune_number_in_set"
            ),
        ),
        migrations.RunPython(create_default_fortune_set, migrations.RunPython.noop),
    ]
