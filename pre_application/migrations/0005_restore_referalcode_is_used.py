from django.db import migrations, models


def add_is_used_column_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'pre_application_referalcode'
    column_name = 'is_used'

    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)

    if table_name not in table_names:
        return

    with connection.cursor() as cursor:
        columns = {
            col.name for col in connection.introspection.get_table_description(cursor, table_name)
        }

    if column_name in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_column = schema_editor.quote_name(column_name)
    schema_editor.execute(
        f'ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} bool NOT NULL DEFAULT FALSE'
    )


def backfill_is_used_from_status(apps, schema_editor):
    ReferalCode = apps.get_model('pre_application', 'ReferalCode')
    ReferalCode.objects.exclude(status='not_used').update(is_used=True)


class Migration(migrations.Migration):

    dependencies = [
        ('pre_application', '0004_merge_0002_enquiry_and_0003_referalcode_admin'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_is_used_column_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='referalcode',
                    name='is_used',
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
        migrations.RunPython(backfill_is_used_from_status, migrations.RunPython.noop),
    ]
