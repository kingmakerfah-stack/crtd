from django.utils import timezone
from datetime import timedelta
from .models import Payment

def expire_old_payments():
    expired = Payment.objects.filter(
        status="created",
        created_at__lt=timezone.now() - timedelta(minutes=15)
    )

    expired.update(status="expired")