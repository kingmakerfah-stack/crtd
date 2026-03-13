from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AdminOTP',
        ),
    ]
