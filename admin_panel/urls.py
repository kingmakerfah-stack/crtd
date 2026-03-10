from django.urls import path
from .views import AdminRegisterView,AdminLoginView, AdminVerifyOTPView

urlpatterns = [
    path("register/", AdminRegisterView.as_view()),
    path("login/", AdminLoginView.as_view()),
    path("verify-otp/", AdminVerifyOTPView.as_view()),
]