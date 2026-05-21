from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PreApplication, ReferalCode


@receiver(post_delete, sender=ReferalCode)
def reset_preapplication_verified_on_referral_delete(sender, instance, **kwargs):
    # Keep verified in sync when a referral is removed from DAP/admin or APIs.
    PreApplication.all_objects.filter(pk=instance.student_id).update(verified=False)
