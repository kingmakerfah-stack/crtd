from django.urls import path
<<<<<<< HEAD
from .views import AdminRegisterView,AdminLoginView, AdminVerifyOTPView

urlpatterns = [
    path("register/", AdminRegisterView.as_view()),
    path("login/", AdminLoginView.as_view()),
    path("verify-otp/", AdminVerifyOTPView.as_view()),
=======
from .views import AdminRegisterView

urlpatterns = [
    path("register/", AdminRegisterView.as_view()),
>>>>>>> c703a367880c5fde76cca46daa7c66a68d5856be
]