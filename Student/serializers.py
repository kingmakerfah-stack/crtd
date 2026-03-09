from rest_framework import serializers
from .models import *


# ---------------------------------------------------------
# Student Serializer
# ---------------------------------------------------------
# Used to create or represent the main Student model.
# This does NOT handle related profile sections.
# profile_completed should ideally be controlled by backend logic.
# ---------------------------------------------------------

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "user",               # Linked Django User (OneToOne)
            "enrollment_id",      # Unique student enrollment ID
            "profile_completed",  # Boolean flag indicating full profile completion
            "is_active",          # Soft activation flag
        ]
        # In production, profile_completed is usually read_only
        # read_only_fields = ["profile_completed"]


# ---------------------------------------------------------
# Student Personal Detail Serializer
# ---------------------------------------------------------
# Handles creation of personal information section.
# Ensures only ONE personal detail object exists per student.
# ---------------------------------------------------------

class StudentPersonalDetailSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = StudentPersonalDetail
        fields = "__all__"  # Includes student foreign key and all personal fields

    def create(self, validated_data):
        """
        Custom create method to prevent duplicate personal detail
        for the same student (OneToOne relationship enforcement).
        """
        student = validated_data.get("student")

        # Check if personal detail already exists
        if StudentPersonalDetail.objects.filter(student=student).exists():
            raise serializers.ValidationError(
                "Personal detail already exists for this student."
            )

        # Create and return new personal detail record
        return StudentPersonalDetail.objects.create(**validated_data)


# ---------------------------------------------------------
# Student Education Serializer
# ---------------------------------------------------------
# Handles educational details section.
# Enforces one education record per student.
# ---------------------------------------------------------

class StudentEducationSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentEducation
        fields = "__all__"

    def create(self, validated_data):
        """
        Prevents creating multiple education records
        for the same student.
        """
        student = validated_data.get("student")

        if StudentEducation.objects.filter(student=student).exists():
            raise serializers.ValidationError(
                "Education record already exists for this student."
            )

        return StudentEducation.objects.create(**validated_data)


# ---------------------------------------------------------
# Student Career Preference Serializer
# ---------------------------------------------------------
# Handles career preference details.
# Ensures only one career preference record per student.
# ---------------------------------------------------------

class StudentCareerPreferenceSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentCareerPreference
        fields = "__all__"

    def create(self, validated_data):
        """
        Prevents duplicate career preference records
        for the same student.
        """
        student = validated_data.get("student")

        if StudentCareerPreference.objects.filter(student=student).exists():
            raise serializers.ValidationError(
                "Career preference already exists for this student."
            )

        return StudentCareerPreference.objects.create(**validated_data)


# ---------------------------------------------------------
# Student OTP Serializer
# ---------------------------------------------------------
# Handles OTP verification for student registration.
# ---------------------------------------------------------

class StudentOTPSerializer(serializers.ModelSerializer):
    """Serializer for StudentOTP model."""
    
    class Meta:
        model = StudentOTP
        fields = ['student', 'otp', 'created_at', 'expires_at', 'is_verified']
        read_only_fields = ['created_at', 'expires_at']


class StudentOTPVerifySerializer(serializers.Serializer):
    """Serializer for verifying StudentOTP code."""
    enrollment_id = serializers.CharField()
    otp = serializers.CharField(max_length=10)