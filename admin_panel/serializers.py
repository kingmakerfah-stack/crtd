from rest_framework import serializers
from accounts.models import CustomUser
from admin_panel.models import AdminUser, AdminOTP


class AdminRegisterSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=AdminUser.ROLE_CHOICES)

    def create(self, validated_data):

        email = validated_data["email"]
        password = validated_data["password"]
        name = validated_data["name"]
        role = validated_data["role"]

        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            role="admin"
        )

        admin = AdminUser.objects.create(
            user=user,
            name=name,
            role=role
        )

        return admin


class AdminLoginSerializer(serializers.Serializer):

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):

        email = data.get("email")
        password = data.get("password")

        try:
            admin = AdminUser.objects.get(user__email=email)
        except AdminUser.DoesNotExist:
            raise serializers.ValidationError("Invalid email")

        user = admin.user

        if not user.check_password(password):
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
            admin = AdminUser.objects.get(user__email=email)
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