from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Module, SubAdminProfile

User = get_user_model()


class RoleBasedRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)
    reference_code = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Reference code returned by referral validation endpoint.",
    )

    class Meta:
        model = User
        fields = [
            'email',
            'password',
            'confirm_password',
            'role',
            'reference_code',
        ]

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
        validated_data.pop('reference_code', None)

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


class OTPVerificationSerializer(serializers.Serializer):
    """Serializer for verifying OTP code."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)
    purpose = serializers.ChoiceField(
        choices=['email_verification', 'password_reset', 'login_otp'],
        default='email_verification',
    )


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for resetting password after OTP has been verified."""
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminLoginVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)


class RBACLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class RBACOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['name', 'display_name', 'order']


class CreateSubAdminSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=8, write_only=True)
    modules = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_modules(self, value):
        valid = Module.objects.filter(name__in=value).values_list('name', flat=True)
        invalid = set(value) - set(valid)
        if invalid:
            raise serializers.ValidationError(f'Invalid modules: {sorted(invalid)}')
        return value


class UpdateSubAdminModulesSerializer(serializers.Serializer):
    modules = serializers.ListField(child=serializers.CharField())


class UpdateSubAdminRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['subadmin', 'sales', 'student'])


class SubAdminListSerializer(serializers.ModelSerializer):
    allowed_modules = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'is_active',
            'created_at',
            'allowed_modules',
            'created_by_name',
        ]

    def get_allowed_modules(self, obj):
        try:
            return obj.subadmin_profile.get_module_names()
        except SubAdminProfile.DoesNotExist:
            return []

    def get_created_by_name(self, obj):
        try:
            return obj.subadmin_profile.created_by.name
        except (SubAdminProfile.DoesNotExist, AttributeError):
            return None


class MeSerializer(serializers.ModelSerializer):
    allowed_modules = serializers.SerializerMethodField()
    can_manage_subadmins = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'role',
            'is_superuser',
            'allowed_modules',
            'can_manage_subadmins',
        ]

    def get_allowed_modules(self, obj):
        if obj.role == 'superadmin':
            return list(Module.objects.filter(is_active=True).values_list('name', flat=True))
        try:
            return obj.subadmin_profile.get_module_names()
        except SubAdminProfile.DoesNotExist:
            return []

    def get_can_manage_subadmins(self, obj):
        if obj.role == 'superadmin':
            return True
        if obj.role != 'subadmin':
            return False
        try:
            return obj.subadmin_profile.has_module_access('sub_admin')
        except SubAdminProfile.DoesNotExist:
            return False