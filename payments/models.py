import random
import string
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from accounts.models import CustomUser
from subscription.models import SubscriptionPlan


def generate_transaction_id():
    return "TXN" + "".join(random.choices(string.digits, k=10))




class Payment(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("expired", "Expired"),
        
    ]


    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    plan = models.ForeignKey(SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,          
        blank=True  
        
    )

    razorpay_order_id = models.CharField(max_length=255, unique=True)

    razorpay_payment_id = models.CharField(max_length=255, unique=True, blank=True, null=True)

    razorpay_signature = models.TextField(null=True, blank=True)

    amount = models.IntegerField()

    currency = models.CharField(max_length=10, default="INR")

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created"
    )

    subscription_start = models.DateTimeField(null=True, blank=True)

    subscription_end = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    # is_active = models.BooleanField(default=False)

    def activate_subscription(self):

    # Always set subscription start
        if not self.subscription_start:
            self.subscription_start = timezone.now()

        # Always set subscription end
        if not self.subscription_end:
            self.subscription_end = timezone.now() + timedelta(days=180)

        self.status = "paid"
        self.save()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(status='paid'),
                name='unique_paid_payment_per_user'
            )
        ]

    def is_active(self):
        return self.subscription_end and timezone.now() < self.subscription_end

    def __str__(self):
        return f"{self.user} - {self.status}"




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
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="history",
        null=True,        #  ADD THIS
        blank=True
    )
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    transaction_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_transaction_id,
    )
    
    
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

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = timezone.now() + timedelta(days=180)

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.transaction_id} - {self.user_id}"


#models for the students subscription functionality
class StudentPayment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    razorpay_order_id = models.CharField(max_length=255, unique=True)
    razorpay_payment_id = models.CharField(max_length=255, null=True, blank=True)
    razorpay_signature = models.TextField(null=True, blank=True)

    amount = models.IntegerField()
    status = models.CharField(max_length=20, default="CREATED")

    created_at = models.DateTimeField(auto_now_add=True)


class StudentSubscription(models.Model):
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payment = models.ForeignKey(StudentPayment, on_delete=models.CASCADE)

    registration_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    status = models.CharField(max_length=20, default="ACTIVE")

    payment_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    renewed_at = models.DateTimeField(auto_now=True)


class RegistrationSequence(models.Model):
    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)