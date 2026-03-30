from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.PositiveSmallIntegerField()
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='INR')
    features = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

    @property
    def final_price(self):
        discount_amount = (self.price * self.discount_percent) / Decimal('100')
        return self.price - discount_amount

    def clean(self):
        if self.price <= 0:
            raise ValidationError({'price': 'Price must be greater than 0.'})

        if self.duration_months <= 0:
            raise ValidationError({'duration_months': 'Duration must be at least 1 month.'})

        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({'discount_percent': 'Discount must be between 0 and 100.'})

        existing_plan = SubscriptionPlan.objects.exclude(pk=self.pk).exists()
        if existing_plan:
            raise ValidationError('Only one subscription plan can exist.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)