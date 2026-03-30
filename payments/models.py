import random
import string
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def generate_transaction_id():
    return "TXN" + "".join(random.choices(string.digits, k=10))


class Payment(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed")
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(
        'subscription.SubscriptionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    razorpay_order_id = models.CharField(max_length=255)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)

    amount = models.IntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created"
    )

    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def activate_subscription(self):
        self.subscription_start = timezone.now()
        self.subscription_end = timezone.now() + timedelta(days=180)
        self.status = "paid"
        self.save()

    def is_active(self):
        if self.subscription_end:
            return timezone.now() < self.subscription_end
        return False

    def __str__(self):
        return f"{self.user}"


class PaymentHistory(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Credit Card'),
        ('upi', 'UPI'),
        ('bank', 'Bank Transfer'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
    ]

    transaction_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_transaction_id,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
    )
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    membership_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    payment_details = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.transaction_id} - {self.user_id}"