from rest_framework import serializers
from .models import *


# ---------------------------------------------------------
# Student Serializer
# ---------------------------------------------------------
class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            "user",
            "enrollment_id",
            "profile_completed",  # ✅ Now exists on model
            "is_active",
        ]
        read_only_fields = ["profile_completed"]  # ✅ Controlled by backend logic only


# ---------------------------------------------------------
# Student Personal Detail Serializer
# ---------------------------------------------------------
class StudentPersonalDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentPersonalDetail
        fields = "__all__"
        # ✅ FIX: student FK is now read-only — injected server-side, not accepted from client
        read_only_fields = ["student"]

    def create(self, validated_data):
        """
        Called only from POST. Prevents duplicate personal detail per student.
        student is injected via view's perform_create / save(student=...).
        """
        student = validated_data.get("student")
        if StudentPersonalDetail.objects.filter(student=student).exists():
            raise serializers.ValidationError(
                "Personal detail already exists for this student."
            )
        return StudentPersonalDetail.objects.create(**validated_data)


# ---------------------------------------------------------
# Student Education Serializer
# ---------------------------------------------------------
class StudentEducationSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentEducation
        fields = "__all__"
        # ✅ FIX: student FK is now read-only
        read_only_fields = ["student"]

    def create(self, validated_data):
        """
        Called only from POST. Prevents duplicate education record per student.
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
class StudentCareerPreferenceSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentCareerPreference
        fields = "__all__"
        # ✅ FIX: student FK is now read-only
        read_only_fields = ["student"]

    def create(self, validated_data):
        """
        Called only from POST. Prevents duplicate career preference per student.
        """
        student = validated_data.get("student")
        if StudentCareerPreference.objects.filter(student=student).exists():
            raise serializers.ValidationError(
                "Career preference already exists for this student."
            )
        return StudentCareerPreference.objects.create(**validated_data)