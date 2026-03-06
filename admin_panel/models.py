from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta
import random



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

    name = models.CharField(max_length=255)

    email = models.EmailField(
        unique=True
    )

    password = models.CharField(
        max_length=255
    )

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

    def save(self, *args, **kwargs):

        if not self.password.startswith("pbkdf2"):
            self.password = make_password(self.password)

        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.email

class AdminOTP(models.Model):

    admin = models.OneToOneField(
        AdminUser,
        on_delete=models.CASCADE,
        related_name="otp"
    )

    otp_code = models.CharField(
        max_length=6
    )

    otp_expiry = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def generate_otp(self):

        otp = str(random.randint(100000, 999999))

        self.otp_code = otp
        self.otp_expiry = timezone.now() + timedelta(minutes=5)

        self.save()

        return otp

    def is_valid(self, otp):

        if self.otp_code == otp and timezone.now() < self.otp_expiry:
            return True

        return False

    def __str__(self):
        return f"{self.admin.email} - OTP {self.otp_code}"

    def __repr__(self):
        return f"<AdminOTP: {self.admin.email} - OTP {self.otp_code}>"
