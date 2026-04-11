from rest_framework import serializers
from django.contrib.auth import get_user_model
from .access_control import get_profile_scope_values
from .models import (
    Module,
    SubAdminModuleAccess,
    SubAdminProfile,
)

User = get_user_model()


MODULE_NAME_ALIASES = {
    'subadmin': 'sub_admin',
    'sub-admin': 'sub_admin',
    'sub admin': 'sub_admin',
}


def normalize_module_name(value):
    normalized = str(value).strip().lower()
    return MODULE_NAME_ALIASES.get(normalized, normalized)


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
    referral_code = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Referral code to bind Google signup to a specific pre-application."
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


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        current_password = attrs['current_password']
        new_password = attrs['new_password']
        confirm_new_password = attrs['confirm_new_password']

        if not user.check_password(current_password):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})

        if new_password != confirm_new_password:
            raise serializers.ValidationError({'confirm_new_password': 'New passwords do not match.'})

        if current_password == new_password:
            raise serializers.ValidationError({'new_password': 'New password must be different from current password.'})

        return attrs


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


class SubAdminModuleAccessInputSerializer(serializers.Serializer):
    module = serializers.CharField()
    can_view = serializers.BooleanField(default=True)
    can_edit = serializers.BooleanField(default=False)

    def validate_module(self, value):
        module_name = normalize_module_name(value)
        if not Module.objects.filter(name=module_name, is_active=True).exists():
            raise serializers.ValidationError(f"Invalid module: {value}")
        return module_name

    def validate(self, attrs):
        if attrs.get('can_edit'):
            attrs['can_view'] = True
        return attrs


class SubAdminModuleAccessSerializer(serializers.ModelSerializer):
    module = serializers.CharField(source='module.name')
    display_name = serializers.CharField(source='module.display_name', read_only=True)

    class Meta:
        model = SubAdminModuleAccess
        fields = ['module', 'display_name', 'can_view', 'can_edit']


class CreateSubAdminSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=100)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    role = serializers.ChoiceField(choices=['subadmin'], default='subadmin')
    is_active = serializers.BooleanField(default=True)
    account_access_start = serializers.DateTimeField(required=False, allow_null=True)
    account_access_end = serializers.DateTimeField(required=False, allow_null=True)
    module_accesses = SubAdminModuleAccessInputSerializer(many=True, required=False)
    birth_states = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    college_states = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    passing_years = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_passing_years(self, value):
        normalized = []
        for year in value:
            year_value = str(year).strip()
            if not year_value.isdigit() or len(year_value) != 4:
                raise serializers.ValidationError('Passing years must be 4-digit values.')
            normalized.append(year_value)
        return normalized

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        account_access_start = attrs.get('account_access_start')
        account_access_end = attrs.get('account_access_end')
        if account_access_start and account_access_end and account_access_start > account_access_end:
            raise serializers.ValidationError('account_access_start must be before account_access_end.')

        module_accesses = attrs.get('module_accesses') or []
        if not module_accesses:
            raise serializers.ValidationError('At least one module assignment is required.')

        module_names = [item['module'] for item in module_accesses]
        if len(module_names) != len(set(module_names)):
            raise serializers.ValidationError('Duplicate module assignments are not allowed.')

        return attrs


class UpdateSubAdminModulesSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    account_access_start = serializers.DateTimeField(required=False, allow_null=True)
    account_access_end = serializers.DateTimeField(required=False, allow_null=True)
    module_accesses = SubAdminModuleAccessInputSerializer(many=True, required=False)
    birth_states = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    college_states = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)
    passing_years = serializers.ListField(child=serializers.CharField(), allow_empty=True, required=False)

    def validate_passing_years(self, value):
        normalized = []
        for year in value:
            year_value = str(year).strip()
            if not year_value.isdigit() or len(year_value) != 4:
                raise serializers.ValidationError('Passing years must be 4-digit values.')
            normalized.append(year_value)
        return normalized

    def validate(self, attrs):
        account_access_start = attrs.get('account_access_start')
        account_access_end = attrs.get('account_access_end')
        if account_access_start and account_access_end and account_access_start > account_access_end:
            raise serializers.ValidationError('account_access_start must be before account_access_end.')

        module_accesses = attrs.get('module_accesses') or []
        if module_accesses:
            module_names = [item['module'] for item in module_accesses]
            if len(module_names) != len(set(module_names)):
                raise serializers.ValidationError('Duplicate module assignments are not allowed.')

        return attrs


class UpdateSubAdminRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['subadmin', 'sales', 'student'])


class SubAdminListSerializer(serializers.ModelSerializer):
    allowed_modules = serializers.SerializerMethodField()
    module_accesses = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    account_access_start = serializers.SerializerMethodField()
    account_access_end = serializers.SerializerMethodField()
    birth_states = serializers.SerializerMethodField()
    college_states = serializers.SerializerMethodField()
    passing_years = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'is_active',
            'created_at',
            'allowed_modules',
            'module_accesses',
            'account_access_start',
            'account_access_end',
            'birth_states',
            'college_states',
            'passing_years',
            'created_by_name',
        ]

    def get_allowed_modules(self, obj):
        try:
            return obj.subadmin_profile.get_module_names()
        except SubAdminProfile.DoesNotExist:
            return []

    def get_module_accesses(self, obj):
        try:
            accesses = obj.subadmin_profile.module_accesses.select_related('module').order_by('module__order', 'module__name')
            return SubAdminModuleAccessSerializer(accesses, many=True).data
        except SubAdminProfile.DoesNotExist:
            return []

    def get_created_by_name(self, obj):
        try:
            return obj.subadmin_profile.created_by.name
        except (SubAdminProfile.DoesNotExist, AttributeError):
            return None

    def get_account_access_start(self, obj):
        try:
            return obj.subadmin_profile.account_access_start
        except SubAdminProfile.DoesNotExist:
            return None

    def get_account_access_end(self, obj):
        try:
            return obj.subadmin_profile.account_access_end
        except SubAdminProfile.DoesNotExist:
            return None

    def get_birth_states(self, obj):
        try:
            return get_profile_scope_values(obj.subadmin_profile)['birth_states']
        except SubAdminProfile.DoesNotExist:
            return []

    def get_college_states(self, obj):
        try:
            return get_profile_scope_values(obj.subadmin_profile)['college_states']
        except SubAdminProfile.DoesNotExist:
            return []

    def get_passing_years(self, obj):
        try:
            return get_profile_scope_values(obj.subadmin_profile)['passing_years']
        except SubAdminProfile.DoesNotExist:
            return []


class MeSerializer(serializers.ModelSerializer):
    allowed_modules = serializers.SerializerMethodField()
    module_accesses = serializers.SerializerMethodField()
    can_manage_subadmins = serializers.SerializerMethodField()
    account_access_start = serializers.SerializerMethodField()
    account_access_end = serializers.SerializerMethodField()
    birth_states = serializers.SerializerMethodField()
    college_states = serializers.SerializerMethodField()
    passing_years = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'role',
            'is_superuser',
            'allowed_modules',
            'module_accesses',
            'account_access_start',
            'account_access_end',
            'birth_states',
            'college_states',
            'passing_years',
            'can_manage_subadmins',
        ]

    def get_allowed_modules(self, obj):
        if obj.role == 'superadmin':
            return list(Module.objects.filter(is_active=True).values_list('name', flat=True))
        try:
            return obj.subadmin_profile.get_module_names(current_only=True)
        except SubAdminProfile.DoesNotExist:
            return []

    def get_module_accesses(self, obj):
        if obj.role == 'superadmin':
            return []
        try:
            accesses = obj.subadmin_profile.module_accesses.select_related('module').order_by('module__order', 'module__name')
            return SubAdminModuleAccessSerializer(accesses, many=True).data
        except SubAdminProfile.DoesNotExist:
            return []

    def get_birth_states(self, obj):
        if obj.role == 'superadmin':
            return []
        try:
            return get_profile_scope_values(obj.subadmin_profile)['birth_states']
        except SubAdminProfile.DoesNotExist:
            return []

    def get_college_states(self, obj):
        if obj.role == 'superadmin':
            return []
        try:
            return get_profile_scope_values(obj.subadmin_profile)['college_states']
        except SubAdminProfile.DoesNotExist:
            return []

    def get_passing_years(self, obj):
        if obj.role == 'superadmin':
            return []
        try:
            return get_profile_scope_values(obj.subadmin_profile)['passing_years']
        except SubAdminProfile.DoesNotExist:
            return []

    def get_account_access_start(self, obj):
        if obj.role == 'superadmin':
            return None
        try:
            return obj.subadmin_profile.account_access_start
        except SubAdminProfile.DoesNotExist:
            return None

    def get_account_access_end(self, obj):
        if obj.role == 'superadmin':
            return None
        try:
            return obj.subadmin_profile.account_access_end
        except SubAdminProfile.DoesNotExist:
            return None

    def get_can_manage_subadmins(self, obj):
        if obj.role == 'superadmin':
            return True
        if obj.role != 'subadmin':
            return False
        try:
            return obj.subadmin_profile.has_module_access('sub_admin', action='edit')
        except SubAdminProfile.DoesNotExist:
            return False
