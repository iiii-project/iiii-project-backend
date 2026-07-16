from django.db import migrations, models


def remove_legacy_block_round(apps, schema_editor):
    model = apps.get_model("divinations", "DivinationSession")
    table = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        columns = {column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table)}
    if "block_round" not in columns:
        return

    field = models.PositiveIntegerField()
    field.set_attributes_from_name("block_round")
    field.model = model
    schema_editor.remove_field(model, field)


class Migration(migrations.Migration):
    dependencies = [("divinations", "0003_divinationsession_user")]

    operations = [migrations.RunPython(remove_legacy_block_round, migrations.RunPython.noop)]
