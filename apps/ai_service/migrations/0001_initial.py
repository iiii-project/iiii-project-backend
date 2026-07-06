from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("divinations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("system", "System"), ("user", "User"), ("assistant", "Assistant")], max_length=20)),
                ("content", models.TextField()),
                ("model_name", models.CharField(blank=True, max_length=100)),
                ("token_count", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "divination_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_messages",
                        to="divinations.divinationsession",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
