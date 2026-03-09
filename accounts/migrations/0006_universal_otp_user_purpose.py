from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_merge_accounts_heads'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailotp',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='email_otps',
                to='accounts.customuser',
            ),
        ),
        migrations.AlterField(
            model_name='emailotp',
            name='purpose',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('email_verification', 'Email Verification'),
                    ('password_reset', 'Password Reset'),
                    ('login_otp', 'Login OTP'),
                ],
                default='email_verification',
            ),
        ),
        migrations.AddConstraint(
            model_name='emailotp',
            constraint=models.UniqueConstraint(
                fields=('user', 'purpose'),
                name='unique_otp_per_user_purpose',
            ),
        ),
    ]
