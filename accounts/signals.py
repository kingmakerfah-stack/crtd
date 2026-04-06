from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomUser


@receiver(post_save, sender=CustomUser)
def sync_superuser_role(sender, instance, created, **kwargs):
    """Keep role aligned when a user is made superuser from admin/management commands."""
    if instance.is_superuser and instance.role != 'superadmin':
        CustomUser.objects.filter(pk=instance.pk).update(role='superadmin')
