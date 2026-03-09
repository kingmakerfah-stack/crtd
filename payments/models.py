from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Payment(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed")
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

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