from django.urls import path

from payments.views import razorpay_webhook

from .views import (
    StudentPaymentInitiateAPIView,
    StudentSubscriptionStatusAPIView,
)


urlpatterns = [
    path("payment/initiate/", StudentPaymentInitiateAPIView.as_view(), name="student-payment-initiate"),
    path("payment/webhook/", razorpay_webhook, name="student-payment-webhook"),
    path("subscription/", StudentSubscriptionStatusAPIView.as_view(), name="student-subscription"),
]
