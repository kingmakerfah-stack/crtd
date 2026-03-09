from django.urls import path
from .views import create_order, verify_payment, razorpay_webhook,payment_test_page

urlpatterns = [
    path("create-order/", create_order, name="create_order"),
    path("verify-payment/", verify_payment, name="verify_payment"),
    path("webhook/", razorpay_webhook, name="razorpay_webhook"),
    path("pay/", payment_test_page, name="payment_test_page"),
    
]