import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("fortunes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DivinationSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("anonymous_user_id", models.CharField(blank=True, max_length=100)),
                ("question", models.TextField()),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("love", "感情"),
                            ("career", "工作"),
                            ("study", "學業"),
                            ("wealth", "財運"),
                            ("health", "健康"),
                            ("family", "家庭"),
                            ("relationship", "人際"),
                            ("travel", "出行"),
                            ("other", "其他"),
                        ],
                        max_length=30,
                    ),
                ),
                ("interaction_mode", models.CharField(choices=[("click", "點擊"), ("motion", "動作辨識")], max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("praying", "Praying"),
                            ("drawing", "Drawing"),
                            ("waiting_for_blocks", "Waiting for blocks"),
                            ("confirmed", "Confirmed"),
                            ("rejected", "Rejected"),
                            ("interpreting", "Interpreting"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="created",
                        max_length=30,
                    ),
                ),
                ("confirmed", models.BooleanField(default=False)),
                ("ai_interpretation", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "fortune",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="fortunes.fortune",
                    ),
                ),
                (
                    "fortune_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="fortunes.fortuneset",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BlockCast",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_number", models.PositiveIntegerField()),
                ("block_one", models.CharField(choices=[("flat", "平面"), ("round", "凸面")], max_length=10)),
                ("block_two", models.CharField(choices=[("flat", "平面"), ("round", "凸面")], max_length=10)),
                ("result", models.CharField(choices=[("sheng", "聖筊"), ("xiao", "笑筊"), ("yin", "陰筊")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "divination_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="block_casts",
                        to="divinations.divinationsession",
                    ),
                ),
            ],
            options={"ordering": ["divination_session", "attempt_number"]},
        ),
        migrations.AddConstraint(
            model_name="blockcast",
            constraint=models.UniqueConstraint(
                fields=("divination_session", "attempt_number"), name="unique_block_attempt_in_session"
            ),
        ),
    ]
