from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterAPIView,
    LoginView,
    OTPRequestView,
    OTPVerificationView,
    PasswordResetView,
    AdminLoginView,
    AdminLoginVerifyOTPView,
)
from .token_serializer import CustomTokenObtainPairView
from .views import GoogleAuthView

urlpatterns = [

    # Registration endpoint
    path('register/', RegisterAPIView.as_view(), name='register'),

    # Custom login endpoint that returns JWT token with extra data (email + role)
    path('login/', LoginView.as_view(), name='token_obtain_pair'),

    # Refresh Access Token
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Google OAuth endpoint
    path('google/', GoogleAuthView.as_view(), name='google_auth'),

    # OTP endpoints for email verification and forgot-password
    path('otp/request/', OTPRequestView.as_view(), name='otp_request'),
    path('otp/verify/', OTPVerificationView.as_view(), name='otp_verify'),

    # Final step of forgot-password: set new password after OTP is verified
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),

    # Admin/Subadmin 2FA login flow
    path('admin/login/', AdminLoginView.as_view(), name='admin_login'),
    path('admin/login/verify-otp/', AdminLoginVerifyOTPView.as_view(), name='admin_login_verify_otp'),
]