from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
import random
from accounts.models import CustomUser


from django.db import models
from accounts.models import CustomUser


class AdminUser(models.Model):

    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("sub_admin", "Sub Admin"),
        ("management", "Management"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="admin_profile"
    )

    name = models.CharField(max_length=255)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.user.email} - {self.role}"

class AdminOTP(models.Model):

    admin = models.OneToOneField(
        AdminUser,
        on_delete=models.CASCADE,
        related_name="otp"
    )

    otp_code = models.CharField(max_length=6)

    otp_expiry = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    def generate_otp(self):

        otp = str(random.randint(100000, 999999))

        self.otp_code = otp
        self.otp_expiry = timezone.now() + timedelta(minutes=5)

        self.save()

        return otp

    def is_valid(self, otp):

        return self.otp_code == otp and timezone.now() < self.otp_expiry

    def __str__(self):
        return f"{self.admin.user.email} - OTP {self.otp_code}"