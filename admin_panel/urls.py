from django.urls import path
from .views import AdminRegisterView, AdminVerifyOTPView

urlpatterns = [
    path("register/", AdminRegisterView.as_view()),
    path("verify-otp/", AdminVerifyOTPView.as_view()),
]