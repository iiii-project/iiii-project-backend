from django.db import migrations


def create_missing_blockcast_table(apps, schema_editor):
    model = apps.get_model("divinations", "BlockCast")
    if model._meta.db_table not in schema_editor.connection.introspection.table_names():
        schema_editor.create_model(model)


class Migration(migrations.Migration):
    dependencies = [("divinations", "0005_remove_legacy_session_columns")]

    operations = [migrations.RunPython(create_missing_blockcast_table, migrations.RunPython.noop)]
