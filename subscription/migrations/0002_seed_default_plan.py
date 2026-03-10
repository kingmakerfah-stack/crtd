from decimal import Decimal

from django.db import migrations


def seed_default_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscription', 'SubscriptionPlan')

    if SubscriptionPlan.objects.exists():
        return

    SubscriptionPlan.objects.create(
        name='CRTD 6 Month Plan',
        description='Single subscription plan for full platform access for 6 months.',
        price=Decimal('2000.00'),
        duration_months=6,
        discount_percent=Decimal('0.00'),
        currency='INR',
        features='Full access to the CRTD platform for six months.',
        is_active=True,
    )


def remove_default_plan(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscription', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(name='CRTD 6 Month Plan').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_plan, remove_default_plan),
    ]