# Generated manually for the account-owned history feature.
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("divinations", "0002_divinationsession_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="divinationsession",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="divination_sessions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
