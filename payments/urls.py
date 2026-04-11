from django.urls import path
from .views import create_order, verify_payment, razorpay_webhook,payment_test_page,PaymentHistoryListView,payment_failed,StudentPaymentInitiateView,StudentSubscriptionView



urlpatterns = [
    #create order urls
    path("create-order/", create_order, name="create_order"),
    #verify payment urls 
    path("verify-payment/", verify_payment, name="verify_payment"),
    #razorpay webhook urls for the payment status update
    path("webhook/", razorpay_webhook, name="razorpay_webhook"),

    #payment failed endpoint to hanlde the payment failure and update the payment status to gfailed int db

    path("payment-failed/", payment_failed),

    
    #to check the api endpoints for the razorpay payment flow 
    #remove once the testing complete and the flow is working fine 
    path("pay/", payment_test_page, name="payment_test_page"),

    # Payment history endpoints
    path("payment-history/", PaymentHistoryListView.as_view(), name="payment-history"),



    path('student/payment/initiate/', StudentPaymentInitiateView.as_view(), name="student_payment_initiate"),
    path('student/subscription/', StudentSubscriptionView.as_view(), name="student_subscription"),

]