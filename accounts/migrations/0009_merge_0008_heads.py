from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_repair_email_verified_column'),
        ('accounts', '0008_restore_email_verified_column'),
    ]

    operations = []
