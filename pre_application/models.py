from django.db import models
from django.db.models import Q
from django.conf import settings
from django.utils import timezone


class EnquiryTokenSequence(models.Model):
    next_value = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Next enquiry token number: {self.next_value}"


class PreApplicationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def with_referral(self):
        return self.select_related("referal_codes")

    def soft_delete(self, user=None, reason=None):
        return self.update(
            is_deleted=True,
            deleted_at=models.functions.Now(),
            deleted_by=user,
            deleted_reason=reason or None,
        )

    def restore(self):
        return self.update(
            is_deleted=False,
            deleted_at=None,
            deleted_by=None,
            deleted_reason=None,
        )


class ActivePreApplicationManager(models.Manager.from_queryset(PreApplicationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().active()


class PreApplication(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_NOT_INTERESTED = "not interested"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_NOT_INTERESTED, "Not Interested"),
    ]

    enquiry_token = models.CharField(
        max_length=9,
        unique=True,
        editable=False,
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    whatsapp_no = models.CharField(max_length=13)
    alternate_phone = models.CharField(max_length=13, blank=True, null=True)
    birthplace_state = models.CharField(max_length=100)
    qualification = models.CharField(max_length=100)
    specialization = models.CharField(max_length=100)
    college_name = models.CharField(max_length=150)
    college_state = models.CharField(max_length=100)
    passing_year = models.CharField(max_length=4)
    preferred_time = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_reason = models.CharField(max_length=255, null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="deleted_preapplications",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ActivePreApplicationManager()
    all_objects = models.Manager.from_queryset(PreApplicationQuerySet)()

    def save(self, *args, **kwargs):
        if self.pk:
            original_token = type(self).all_objects.filter(pk=self.pk).values_list(
                "enquiry_token",
                flat=True,
            ).first()
            if original_token and self.enquiry_token != original_token:
                raise ValueError("enquiry_token cannot be modified once created.")
        elif not self.enquiry_token:
            from .services import allocate_next_enquiry_token

            self.enquiry_token = allocate_next_enquiry_token()

        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["email"], name="preapp_email_idx"),
            models.Index(fields=["is_deleted"], name="preapp_deleted_idx"),
            models.Index(fields=["created_at"], name="preapp_created_idx"),
            models.Index(fields=["is_deleted", "created_at"], name="preapp_del_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(is_deleted=False),
                name="uniq_active_preapp_email",
            ),
        ]

    def __str__(self):
        return f"{self.enquiry_token} - {self.first_name} {self.last_name}".strip()

    def soft_delete(self, user=None, reason=None):
        if self.is_deleted:
            if reason is not None:
                self.deleted_reason = reason or None
                self.save(update_fields=["deleted_reason"])
            return

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.deleted_reason = reason or None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "deleted_reason"])

    def restore(self):
        if not self.is_deleted:
            return

        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.deleted_reason = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "deleted_reason"])


class ReferalCode(models.Model):
    STATUS_NOT_USED = 'not_used'
    STATUS_ACCOUNT_CREATED = 'account_created'
    STATUS_MEMBERSHIP_PENDING = 'membership_pending'
    STATUS_MEMBERSHIP_COMPLETED = 'membership_completed'

    STATUS_CHOICES = [
        (STATUS_NOT_USED, 'Account Not Created'),
        (STATUS_ACCOUNT_CREATED, 'Account Created'),
        (STATUS_MEMBERSHIP_PENDING, 'Membership Not Completed'),
        (STATUS_MEMBERSHIP_COMPLETED, 'Membership Completed'),
    ]

    student = models.OneToOneField(
        PreApplication,
        on_delete=models.CASCADE,
        related_name="referal_codes",
    )
    code = models.CharField(max_length=10, unique=True)
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_USED,
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_codes',
        null=True,
        blank=True,
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="referral_status_idx"),
        ]

    def __str__(self):
        return f"{self.code} -> {self.student.enquiry_token}"
