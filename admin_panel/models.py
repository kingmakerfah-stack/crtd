from django.db import models
from django.utils import timezone
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
        related_name='otp',
    )
    otp_code = models.CharField(max_length=6)
    otp_expiry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.otp_expiry
