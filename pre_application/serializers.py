import re

from rest_framework import serializers

from .models import PreApplication, ReferalCode


class PreApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreApplication
        fields = "__all__"
        read_only_fields = [
            "enquiry_token",
            "verified",
            "created_at",
            "status",
            "is_deleted",
            "deleted_at",
            "deleted_reason",
            "deleted_by",
        ]

    def validate_first_name(self, value):
        value = value.strip()

        if not re.match(r"^[A-Za-z\s]+$", value):
            raise serializers.ValidationError(
                "First name must contain only letters."
            )

        if len(value) < 2:
            raise serializers.ValidationError(
                "First name must be at least 2 characters."
            )

        return value

    def validate_last_name(self, value):
        value = value.strip()

        if not re.match(r"^[A-Za-z\s]+$", value):
            raise serializers.ValidationError(
                "Last name must contain only letters."
            )

        return value

    def validate_whatsapp_no(self, value):
        pattern = r"^(?:\+91)?[6-9]\d{9}$"

        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Enter a valid Indian mobile number."
            )

        return value

    def validate_alternate_phone(self, value):
        if value:
            pattern = r"^(?:\+91)?[6-9]\d{9}$"

            if not re.match(pattern, value):
                raise serializers.ValidationError(
                    "Enter a valid Indian mobile number."
                )

        return value

    def validate_email(self, value):
        instance = getattr(self, "instance", None)

        if instance:
            if PreApplication.objects.filter(email=value).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError(
                    "Application with this email already exists."
                )
        else:
            if PreApplication.objects.filter(email=value).exists():
                raise serializers.ValidationError(
                    "Application with this email already exists."
                )

        return value


class ReferalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferalCode
        fields = ["id", "student", "code", "status", "is_used", "created_at"]
        read_only_fields = ["student", "code", "status", "is_used", "created_at"]


class PreApplicationLookupSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    reference_code = serializers.SerializerMethodField()

    class Meta:
        model = PreApplication
        fields = [
            "id",
            "enquiry_token",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "whatsapp_no",
            "alternate_phone",
            "verified",
            "reference_code",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_reference_code(self, obj):
        referral = getattr(obj, "referal_codes", None)
        return referral.code if referral else None


class PreApplicationAdminListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    reference_code = serializers.SerializerMethodField()

    class Meta:
        model = PreApplication
        fields = [
            "id",
            "enquiry_token",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "whatsapp_no",
            "alternate_phone",
            "birthplace_state",
            "qualification",
            "specialization",
            "college_name",
            "college_state",
            "passing_year",
            "preferred_time",
            "status",
            "verified",
            "is_deleted",
            "deleted_at",
            "deleted_reason",
            "deleted_by",
            "reference_code",
            "created_at",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_reference_code(self, obj):
        referral = getattr(obj, "referal_codes", None)
        return referral.code if referral else None


class PreApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreApplication
        fields = ["status"]


class PreApplicationArchiveRequestSerializer(serializers.Serializer):
    deleted_reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PreApplicationActionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    enquiry_token = serializers.CharField()
    is_deleted = serializers.BooleanField()


class ReferralValidationResponseSerializer(PreApplicationLookupSerializer):
    class Meta(PreApplicationLookupSerializer.Meta):
        fields = PreApplicationLookupSerializer.Meta.fields
