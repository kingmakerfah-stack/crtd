import random
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError
from django.db import close_old_connections
from django.db.utils import OperationalError, InterfaceError
from .models import AdminOTP


def generate_admin_otp(admin):
    for attempt in range(2):
        try:
            close_old_connections()
            now = timezone.now()
            otp_obj = AdminOTP.objects.filter(admin=admin).first()

            # Infer last OTP issue time from expiry (expiry = issued_at + 5 minutes).
            if otp_obj and otp_obj.otp_expiry:
                last_issued_at = otp_obj.otp_expiry - timedelta(minutes=5)
                if now - last_issued_at < timedelta(seconds=60):
                    raise ValidationError("Please wait before requesting another OTP")

            otp = str(random.randint(100000, 999999))
            expiry = now + timedelta(minutes=5)

            AdminOTP.objects.update_or_create(
                admin=admin,
                defaults={
                    "otp_code": otp,
                    "otp_expiry": expiry,
                },
            )
            return otp
        except (OperationalError, InterfaceError):
            if attempt == 1:
                raise
            close_old_connections()
