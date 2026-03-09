from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Student', '0002_studentotp'),
    ]

    operations = [
        migrations.DeleteModel(
            name='StudentOTP',
        ),
    ]
