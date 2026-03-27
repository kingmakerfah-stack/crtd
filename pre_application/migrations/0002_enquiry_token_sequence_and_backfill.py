from django.db import migrations, models


def backfill_enquiry_tokens(apps, schema_editor):
    PreApplication = apps.get_model("pre_application", "PreApplication")
    EnquiryTokenSequence = apps.get_model("pre_application", "EnquiryTokenSequence")

    next_value = 1
    for pre_application in PreApplication.objects.order_by("pk"):
        pre_application.enquiry_token = f"ENQ{next_value:06d}"
        pre_application.save(update_fields=["enquiry_token"])
        next_value += 1

    EnquiryTokenSequence.objects.update_or_create(
        pk=1,
        defaults={"next_value": next_value},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pre_application", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnquiryTokenSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("next_value", models.PositiveIntegerField(default=1)),
            ],
        ),
        migrations.AddField(
            model_name="preapplication",
            name="enquiry_token",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=9,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_enquiry_tokens, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS pre_application_preapplication_enquiry_token_9607cabb_like;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="preapplication",
            name="enquiry_token",
            field=models.CharField(
                editable=False,
                max_length=9,
                unique=True,
            ),
        ),
    ]
