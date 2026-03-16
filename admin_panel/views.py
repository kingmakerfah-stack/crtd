from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import AdminRegisterSerializer, AdminOTPVerifySerializer
from .services import generate_admin_otp
from .tasks import send_admin_otp_email
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from admin_panel.models import AdminOTP, AdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer as  AdminLoginSerializer


class AdminRegisterView(APIView):

    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=AdminRegisterSerializer)
    def post(self, request):

        serializer = AdminRegisterSerializer(data=request.data)

        if serializer.is_valid():

            admin = serializer.save()

            otp = generate_admin_otp(admin)

            send_admin_otp_email(admin.user.email, otp)

            return Response(
                {"message": "Admin registered. OTP sent to email."},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=400)

        return Response(serializer.errors, status=400)
class AdminLoginView(APIView):

    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=AdminLoginSerializer)
    def post(self, request):

        serializer = AdminLoginSerializer(data=request.data)

        if serializer.is_valid():

            admin = serializer.validated_data["admin"]
            user = admin.user

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Login successful",
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=400)


class AdminVerifyOTPView(APIView):

    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=AdminOTPVerifySerializer)
    def post(self, request):

        serializer = AdminOTPVerifySerializer(data=request.data)

        if serializer.is_valid():

            return Response(
                {"message": "Email verified successfully"}
            )

        return Response(serializer.errors, status=400)
