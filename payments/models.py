from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid

from subscription.models import SubscriptionPlan


def generate_transaction_id():
        return f"TRX-{uuid.uuid4().hex[:6].upper()}"

class Payment(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    plan=models.ForeignKey(SubscriptionPlan,on_delete=models.SET_NULL,null=True,blank=True)

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
        self.subscription_end = timezone.now() + timedelta(days=180)  #6-month subscription
        self.status = "paid"
        self.save()

    def is_active(self):
        if self.subscription_end:
            return timezone.now() < self.subscription_end
        return False

    def __str__(self):
        return f"{self.user}"
    

class PaymentHistory(models.Model):

    PAYMENT_METHOD_CHOICES=[
        ('card',"Credit Card"),
        ('upi',"UPI"),
        ('bank','Bank Transfer'),
    ]


    STATUS_CHOICES = [
        ("completed", "Completed"),
        ("pending", "Pending"),
        ("failed", "Failed"),
    ]


    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)

    transaction_id=models.CharField(max_length=20,
    unique=True,
    default=generate_transaction_id
    )

    amount=models.DecimalField(max_digits=6,decimal_places=2)

    payment_method=models.CharField(max_length=20,choices=PAYMENT_METHOD_CHOICES)

    payment_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')

    razorpay_payment_id=models.CharField(max_length=255,blank=True,null=True)

    registration_date=models.DateTimeField(auto_now_add=True)

    end_date=models.DateTimeField(null=True,blank=True)

    membership_id=models.UUIDField(default=uuid.uuid4,editable=False,unique=True)

    payment_details=models.TextField(blank=True,null=True)


    def save(self, *args, **kwargs):

        if not self.end_date:
            self.end_date = timezone.now() + timedelta(days=180)

        super().save(*args, **kwargs)

    
    class Meta:
        ordering=['-registration_date']


    def __str__(self):
        return f"{self.user} - {self.transaction_id}"


