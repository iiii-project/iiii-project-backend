from django.db import migrations, models


def remove_legacy_message_columns(apps, schema_editor):
    model = apps.get_model("ai_service", "AIMessage")
    table = model._meta.db_table
    expected_columns = {field.column for field in model._meta.local_fields}
    with schema_editor.connection.cursor() as cursor:
        actual_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(cursor, table)
        }

    for column_name in actual_columns - expected_columns:
        field = models.IntegerField()
        field.set_attributes_from_name(column_name)
        field.model = model
        schema_editor.remove_field(model, field)


class Migration(migrations.Migration):
    dependencies = [("ai_service", "0001_initial")]

    operations = [migrations.RunPython(remove_legacy_message_columns, migrations.RunPython.noop)]
