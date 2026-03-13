from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class RoleBasedRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'role']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "This email is already registered."
            )
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError(
                "Passwords do not match."
            )
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role']
        )

        return user


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=False,
        allow_null=True
    )


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for requesting an OTP email (verification or password reset)."""
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=['email_verification', 'password_reset', 'login_otp'],
        default='email_verification',
    )

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "No user found with this email address."
            )
        return value


class OTPVerificationSerializer(serializers.Serializer):
    """Serializer for verifying OTP code."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)
    purpose = serializers.ChoiceField(
        choices=['email_verification', 'password_reset', 'login_otp'],
        default='email_verification',
    )

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "No user found with this email address."
            )
        return value


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for resetting password after OTP has been verified."""
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "No user found with this email address."
            )
        return value


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminLoginVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)