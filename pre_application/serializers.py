from rest_framework import serializers 
from .models import PreApplication , ReferalCode
import re

class PreApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreApplication
        fields = "__all__"
        read_only_fields = ["created_at"]

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
        pattern = r'^(?:\+91)?[6-9]\d{9}$'

        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Enter a valid Indian mobile number."
            )

        return value

    def validate_alternate_phone(self, value):
        if value:
            pattern = r'^(?:\+91)?[6-9]\d{9}$'

            if not re.match(pattern, value):
                raise serializers.ValidationError(
                    "Enter a valid Indian mobile number."
                )

        return value

    def validate_email(self, value):
        instance = getattr(self, 'instance', None)

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

import random
import string
from .models import ReferalCode


class ReferalCodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReferalCode
        fields = ['id', 'student', 'code', 'is_used', 'created_at']
        read_only_fields = ['code', 'is_used', 'created_at']

    def generate_unique_code(self, length=8):
        """
        Generate a unique referral code.
        """

        while True:
            code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=length)
            )

            if not ReferalCode.objects.filter(code=code).exists():
                return code

    def create(self, validated_data):
        """
        Override create to auto-generate unique referral code.
        """

        validated_data['code'] = self.generate_unique_code()

        return ReferalCode.objects.create(**validated_data)
