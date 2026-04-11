from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone


def normalize_scope_value(value):
    return " ".join((value or "").strip().split())


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
        choices=ROLE_CHOICES,
        db_index=True,
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
    expires_at = models.DateTimeField(db_index=True)
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
    is_active = models.BooleanField(default=True, db_index=True)
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
    account_access_start = models.DateTimeField(null=True, blank=True)
    account_access_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_subadmin_profile'
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(account_access_start__isnull=True)
                    | models.Q(account_access_end__isnull=True)
                    | models.Q(account_access_start__lte=models.F('account_access_end'))
                ),
                name='subadmin_account_window_valid',
            ),
        ]

    def get_module_names(self, current_only=False, at_time=None):
        module_accesses = self.module_accesses.select_related('module').filter(
            can_view=True,
            module__is_active=True,
        )
        module_names = list(module_accesses.values_list('module__name', flat=True))
        if module_names:
            return module_names
        return list(self.allowed_modules.values_list('name', flat=True))

    def is_account_access_active(self, at_time=None):
        current_time = at_time or timezone.now()
        if not self.is_active or not self.user.is_active:
            return False
        if self.account_access_start and current_time < self.account_access_start:
            return False
        if self.account_access_end and current_time > self.account_access_end:
            return False
        return True

    def has_module_access(self, module_name, action='view', at_time=None):
        if not self.is_account_access_active(at_time=at_time):
            return False

        module_accesses = self.module_accesses.select_related('module').filter(
            module__name=module_name,
            module__is_active=True,
        )

        if module_accesses.exists():
            if action == 'edit':
                return module_accesses.filter(can_edit=True).exists()
            return module_accesses.filter(can_view=True).exists()

        if action == 'edit':
            return False
        return self.allowed_modules.filter(name=module_name, is_active=True).exists()

    def __str__(self):
        return f"SubAdmin: {self.user.email}"


class SubAdminModuleAccess(models.Model):
    subadmin_profile = models.ForeignKey(
        SubAdminProfile,
        on_delete=models.CASCADE,
        related_name='module_accesses',
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='subadmin_accesses',
    )
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_subadmin_module_access'
        constraints = [
            models.UniqueConstraint(
                fields=['subadmin_profile', 'module'],
                name='uniq_subadmin_module_access',
            ),
            models.CheckConstraint(
                check=models.Q(can_edit=False) | models.Q(can_view=True),
                name='subadmin_module_edit_implies_view',
            ),
        ]
        indexes = [
            models.Index(fields=['subadmin_profile', 'module'], name='subadmin_module_idx'),
            models.Index(fields=['module', 'can_view'], name='subadmin_module_view_idx'),
            models.Index(fields=['module', 'can_edit'], name='subadmin_module_edit_idx'),
        ]

    def is_currently_active(self, at_time=None):
        if not self.module.is_active:
            return False
        return self.can_view

    def __str__(self):
        return f"{self.subadmin_profile.user.email} -> {self.module.name}"


class SubAdminBirthStateScope(models.Model):
    subadmin_profile = models.ForeignKey(
        SubAdminProfile,
        on_delete=models.CASCADE,
        related_name='birth_state_scopes',
    )
    state_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'accounts_subadmin_birth_state_scope'
        constraints = [
            models.UniqueConstraint(
                fields=['subadmin_profile', 'state_name'],
                name='uniq_subadmin_birth_state_scope',
            ),
        ]
        indexes = [
            models.Index(fields=['subadmin_profile', 'state_name'], name='subadmin_birth_scope_idx'),
        ]

    def save(self, *args, **kwargs):
        self.state_name = normalize_scope_value(self.state_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subadmin_profile.user.email} birth:{self.state_name}"


class SubAdminCollegeStateScope(models.Model):
    subadmin_profile = models.ForeignKey(
        SubAdminProfile,
        on_delete=models.CASCADE,
        related_name='college_state_scopes',
    )
    state_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'accounts_subadmin_college_state_scope'
        constraints = [
            models.UniqueConstraint(
                fields=['subadmin_profile', 'state_name'],
                name='uniq_subadmin_college_state_scope',
            ),
        ]
        indexes = [
            models.Index(fields=['subadmin_profile', 'state_name'], name='subadmin_college_scope_idx'),
        ]

    def save(self, *args, **kwargs):
        self.state_name = normalize_scope_value(self.state_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subadmin_profile.user.email} college:{self.state_name}"


class SubAdminPassingYearScope(models.Model):
    subadmin_profile = models.ForeignKey(
        SubAdminProfile,
        on_delete=models.CASCADE,
        related_name='passing_year_scopes',
    )
    passing_year = models.CharField(max_length=4)

    class Meta:
        db_table = 'accounts_subadmin_passing_year_scope'
        constraints = [
            models.UniqueConstraint(
                fields=['subadmin_profile', 'passing_year'],
                name='uniq_subadmin_passing_year_scope',
            ),
        ]
        indexes = [
            models.Index(fields=['subadmin_profile', 'passing_year'], name='subadmin_year_scope_idx'),
        ]

    def save(self, *args, **kwargs):
        self.passing_year = normalize_scope_value(self.passing_year)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subadmin_profile.user.email} year:{self.passing_year}"
