from rest_framework import serializers
from .models import AdminUser, AdminOTP


class AdminLoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        email = data.get("email")
        password = data.get("password")

        try:
            admin = AdminUser.objects.get(email=email)

        except AdminUser.DoesNotExist:
            raise serializers.ValidationError("Invalid email")

        if not admin.check_password(password):
            raise serializers.ValidationError("Invalid password")

        if admin.status != "active":
            raise serializers.ValidationError("Admin is inactive")

        data["admin"] = admin
        return data
    
class AdminOTPVerifySerializer(serializers.Serializer):

    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):

        email = data.get("email")
        otp = data.get("otp")

        try:
            admin = AdminUser.objects.get(email=email)
        except AdminUser.DoesNotExist:
            raise serializers.ValidationError("Admin not found")

        try:
            otp_obj = AdminOTP.objects.get(admin=admin)
        except AdminOTP.DoesNotExist:
            raise serializers.ValidationError("OTP not generated")

        if not otp_obj.is_valid(otp):
            raise serializers.ValidationError("Invalid or expired OTP")

        data["admin"] = admin
        return data    