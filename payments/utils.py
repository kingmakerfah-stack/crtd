from django.utils import timezone
from datetime import timedelta
from .models import Payment

from django.db import transaction
from datetime import datetime
from .models import RegistrationSequence

def expire_old_payments():
    expired = Payment.objects.filter(
        status="created",
        created_at__lt=timezone.now() - timedelta(minutes=15)
    )

    expired.update(status="expired")


#CREATE REGISTRATION NUMBER LOGIC
def generate_registration_number():
    year = datetime.now().year

    with transaction.atomic():
        seq, _ = RegistrationSequence.objects.select_for_update().get_or_create(year=year)
        seq.last_number += 1
        seq.save()

        return f"CRTD{year}{seq.last_number:06d}"