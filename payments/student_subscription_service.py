from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import transaction

from payments.models import StudentPayment, StudentSubscription
from payments.utils import generate_registration_number


def _subscription_duration_months():
    value = int(getattr(settings, "SUBSCRIPTION_DURATION_MONTHS", 6) or 6)
    return max(value, 1)


def get_student_subscription(user, lock=False):
    queryset = StudentSubscription.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(student=user).first()


def expire_subscription_if_needed(subscription):
    if not subscription:
        return None

    today = date.today()
    if (
        subscription.status == StudentSubscription.STATUS_ACTIVE
        and subscription.expiry_date
        and subscription.expiry_date < today
    ):
        subscription.status = StudentSubscription.STATUS_EXPIRED
        subscription.save(update_fields=["status", "renewed_at"])
    return subscription


def has_active_subscription(user):
    subscription = expire_subscription_if_needed(get_student_subscription(user))
    if not subscription:
        return False

    return (
        subscription.status == StudentSubscription.STATUS_ACTIVE
        and subscription.expiry_date is not None
        and subscription.expiry_date >= date.today()
    )


def build_subscription_summary(user):
    subscription = expire_subscription_if_needed(get_student_subscription(user))
    if not subscription:
        return {
            "is_paid": False,
            "status": None,
            "registration_number": None,
            "payment_date": None,
            "expiry_date": None,
            "days_remaining": 0,
        }

    if subscription.expiry_date:
        days_remaining = max((subscription.expiry_date - date.today()).days, 0)
    else:
        days_remaining = 0

    return {
        "is_paid": subscription.status == StudentSubscription.STATUS_ACTIVE and days_remaining >= 0,
        "status": subscription.status,
        "registration_number": subscription.registration_number,
        "payment_date": subscription.payment_date,
        "expiry_date": subscription.expiry_date,
        "days_remaining": days_remaining,
    }


@transaction.atomic
def activate_subscription_from_student_payment(student_payment):
    subscription = get_student_subscription(student_payment.student, lock=True)
    if not subscription:
        subscription = StudentSubscription.objects.create(student=student_payment.student)

    if not subscription.registration_number:
        subscription.registration_number = generate_registration_number()

    today = date.today()
    subscription.student_payment = student_payment
    subscription.status = StudentSubscription.STATUS_ACTIVE
    subscription.payment_date = today
    subscription.expiry_date = today + relativedelta(months=_subscription_duration_months())
    subscription.save()

    return subscription


@transaction.atomic
def mark_student_payment_success(order_id, payment_id=None, signature=None):
    payment = StudentPayment.objects.select_for_update().get(razorpay_order_id=order_id)
    if payment.status == StudentPayment.STATUS_SUCCESS:
        return payment, False

    payment.status = StudentPayment.STATUS_SUCCESS
    if payment_id:
        payment.razorpay_payment_id = payment_id
    if signature:
        payment.razorpay_signature = signature
    payment.save(update_fields=["status", "razorpay_payment_id", "razorpay_signature", "updated_at"])
    return payment, True


@transaction.atomic
def mark_student_payment_failed(order_id, payment_id=None):
    payment = StudentPayment.objects.select_for_update().filter(razorpay_order_id=order_id).first()
    if not payment:
        return None

    if payment.status == StudentPayment.STATUS_SUCCESS:
        return payment

    payment.status = StudentPayment.STATUS_FAILED
    if payment_id:
        payment.razorpay_payment_id = payment_id
    payment.save(update_fields=["status", "razorpay_payment_id", "updated_at"])
    return payment
