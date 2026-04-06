from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone


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
        ('superadmin', 'Super Admin'),
        ('sales', 'Sales'),
        ('student', 'Student'),
        ('company', 'Company'),
        ('admin', 'Admin'),
        ('subadmin', 'Subadmin'),
    )

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True, default='')

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} - {self.role}"


class EmailOTP(models.Model):
    """
    Model to store OTPs for email verification and password reset.

    Each OTP is associated with a user and a purpose (email_verification
    or password_reset). Uses update_or_create so a resend always refreshes
    the same record instead of creating duplicates.
    Old OTPs are cleaned up periodically by the cleanup_expired_otps Celery task.
    """

    PURPOSE_EMAIL_VERIFICATION = 'email_verification'
    PURPOSE_PASSWORD_RESET = 'password_reset'
    PURPOSE_LOGIN_OTP = 'login_otp'
    PURPOSE_CHOICES = (
        (PURPOSE_EMAIL_VERIFICATION, 'Email Verification'),
        (PURPOSE_PASSWORD_RESET, 'Password Reset'),
        (PURPOSE_LOGIN_OTP, 'Login OTP'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_otps')
    otp = models.CharField(max_length=255) # Store hashed OTP
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    purpose = models.CharField(
        max_length=30,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_EMAIL_VERIFICATION,
    )

    class Meta:
        db_table = 'accounts_email_otp'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'purpose'],
                name='unique_otp_per_user_purpose'
            ),
        ]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.user.email}"
    
    def is_valid(self):
        """Check if OTP is still valid (not expired and not yet used)."""
        return not self.is_verified and not self.is_expired()


class Module(models.Model):
    MODULE_CHOICES = [
        ('dashboard', 'Dashboard'),
        ('web_update', 'Web Update'),
        ('enquiry_form', 'Enquiry Form'),
        ('reference_code', 'Reference Code'),
        ('sub_admin', 'Sub Admin'),
        ('total_user_status', 'Total User Status'),
        ('analytics', 'Analytics'),
        ('payment', 'Payment'),
        ('job_applications', 'Job Applications'),
        ('membership', 'Membership'),
        ('employee_status', 'Employee Status'),
        ('sales', 'Sales'),
    ]

    name = models.CharField(max_length=50, unique=True, choices=MODULE_CHOICES)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'accounts_module'
        ordering = ['order']

    def __str__(self):
        return self.display_name


class SubAdminProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='subadmin_profile',
    )
    allowed_modules = models.ManyToManyField(Module, blank=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_subadmins',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_subadmin_profile'

    def get_module_names(self):
        return list(self.allowed_modules.values_list('name', flat=True))

    def has_module_access(self, module_name):
        return self.allowed_modules.filter(name=module_name, is_active=True).exists()

    def __str__(self):
        return f"SubAdmin: {self.user.email}"