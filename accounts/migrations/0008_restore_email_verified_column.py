from django.db import migrations


def restore_email_verified_column(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'accounts_customuser'
    column_name = 'email_verified'

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
        f'ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} bool NOT NULL DEFAULT 0'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_alter_customuser_role'),
    ]

    operations = [
        migrations.RunPython(restore_email_verified_column, migrations.RunPython.noop),
    ]
