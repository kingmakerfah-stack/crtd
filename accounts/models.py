from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
# from django.utils import timezone
# from datetime import timedelta


class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not password:
            raise ValueError("Superuser must have a password")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):

    ROLE_CHOICES = (
        ('student', 'Student'),
        ('company', 'Company'),
        ('admin', 'Admin'),
    )

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} - {self.role}"


# class EmailOTP(models.Model):
#     """
#     Model to store OTPs for email verification.
    
#     Each OTP is associated with a user and has an expiration time.
#     Old OTPs should be cleaned up periodically.
#     """
#     user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='email_otp')
#     otp = models.CharField(max_length=10)
#     created_at = models.DateTimeField(auto_now_add=True)
#     expires_at = models.DateTimeField()
#     is_verified = models.BooleanField(default=False)

#     class Meta:
#         db_table = 'accounts_email_otp'

#     def __str__(self):
#         return f"OTP for {self.user.email}"
    
#     def is_valid(self):
#         """Check if OTP is still valid (not expired and not yet used)."""
#         return not self.is_verified and timezone.now() < self.expires_at
    
#     def is_expired(self):
#         """Check if OTP has expired."""
#         return timezone.now() > self.expires_at