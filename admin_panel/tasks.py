try:
    from celery import shared_task
except ModuleNotFoundError:
    from utils.celery_compat import shared_task
from django.core.mail import send_mail


@shared_task
def send_admin_otp_email(email, otp):

    send_mail(
        subject="Admin OTP Verification",
        message=f"Your OTP is {otp}",
        from_email="noreply@crtd.com",
        recipient_list=[email],
    )

@shared_task
def delete_expired_admin_otps():

    from django.utils import timezone
    from admin_panel.models import AdminOTP

    AdminOTP.objects.filter(
        otp_expiry__lt=timezone.now()
    ).delete()    
