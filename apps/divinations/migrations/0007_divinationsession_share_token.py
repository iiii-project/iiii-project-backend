import uuid

from django.db import migrations, models


def create_share_tokens(apps, schema_editor):
    DivinationSession = apps.get_model("divinations", "DivinationSession")
    for session in DivinationSession.objects.filter(share_token__isnull=True).iterator():
        session.share_token = uuid.uuid4()
        session.save(update_fields=["share_token"])


class Migration(migrations.Migration):
    dependencies = [("divinations", "0006_create_missing_blockcast_table")]

    operations = [
        migrations.AddField(
            model_name="divinationsession",
            name="share_token",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(create_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="divinationsession",
            name="share_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
