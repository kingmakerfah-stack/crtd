from django.urls import path
from .views import (
    create_order,
    verify_payment,
    PaymentHistoryListView,
    payment_failed,
    StudentSubscriptionView,
    razorpay_webhook,
)



urlpatterns = [
    path("create-order/", create_order, name="create_order"),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("webhook/", razorpay_webhook, name="razorpay_webhook"),
    path("payment-failed/", payment_failed, name="payment_failed"),
    path("payment-history/", PaymentHistoryListView.as_view(), name="payment-history"),
    path("student/subscription/", StudentSubscriptionView.as_view(), name="student_subscription"),

]