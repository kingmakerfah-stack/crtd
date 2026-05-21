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
        normalized_email = value.strip().lower()
        active_queryset = PreApplication.objects
        all_queryset = PreApplication.all_objects
        instance = getattr(self, "instance", None)

        deleted_queryset = all_queryset.filter(email__iexact=normalized_email, is_deleted=True)

        if instance:
            deleted_queryset = deleted_queryset.exclude(pk=instance.pk)

        if deleted_queryset.exists():
            raise serializers.ValidationError(
                "A deleted pre-application already exists for this email. Please ask admin to restore it."
            )

        if instance:
            if active_queryset.filter(email__iexact=normalized_email).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError(
                    "Application with this email already exists."
                )
        else:
            if active_queryset.filter(email__iexact=normalized_email).exists():
                raise serializers.ValidationError(
                    "Application with this email already exists."
                )

        return normalized_email


class ReferalCodeSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ReferalCode
        fields = ["id", "student", "code", "status", "is_used", "admin", "created_by_email", "created_at"]
        read_only_fields = ["student", "code", "status", "is_used", "admin", "created_by_email", "created_at"]

    def get_created_by_email(self, obj):
        return obj.admin.email if obj.admin else None


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
    status = serializers.CharField()

    class Meta:
        model = PreApplication
        fields = ["status"]

    def validate_status(self, value):
        normalized = str(value).strip().lower().replace("_", " ")

        status_aliases = {
            "pending": PreApplication.STATUS_PENDING,
            "completed": PreApplication.STATUS_COMPLETED,
            "enquiry done": PreApplication.STATUS_COMPLETED,
            "done": PreApplication.STATUS_COMPLETED,
            "not interested": PreApplication.STATUS_NOT_INTERESTED,
        }

        mapped = status_aliases.get(normalized)
        if not mapped:
            raise serializers.ValidationError(
                "Invalid status. Allowed values: pending, completed, not interested."
            )

        return mapped


class PreApplicationArchiveRequestSerializer(serializers.Serializer):
    deleted_reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PreApplicationActionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    enquiry_token = serializers.CharField()
    is_deleted = serializers.BooleanField()


class ReferralValidationResponseSerializer(PreApplicationLookupSerializer):
    class Meta(PreApplicationLookupSerializer.Meta):
        fields = PreApplicationLookupSerializer.Meta.fields
