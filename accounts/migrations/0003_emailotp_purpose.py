from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_customuser_email_verified_emailotp'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailotp',
            name='purpose',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('email_verification', 'Email Verification'),
                    ('password_reset', 'Password Reset'),
                ],
                default='email_verification',
            ),
        ),
    ]
