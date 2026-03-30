from django.db import migrations


def add_email_verified_column_if_missing(apps, schema_editor):
    table_name = "accounts_customuser"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        columns = [
            column.name
            for column in connection.introspection.get_table_description(
                cursor, table_name
            )
        ]

    if "email_verified" in columns:
        return

    schema_editor.execute(
        f"ALTER TABLE {schema_editor.quote_name(table_name)} "
        "ADD COLUMN email_verified bool NOT NULL DEFAULT 0"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_alter_customuser_role"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_email_verified_column_if_missing,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[],
        ),
    ]
