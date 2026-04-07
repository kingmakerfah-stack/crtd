from rest_framework import serializers
from .models import Job

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = "__all__"

    def validate_total_vacancies(self, value):
        if value < 1:
            raise serializers.ValidationError("Total vacancies must be at least 1")
        return value

    def validate_job_role(self, value):
        if not value.strip():
            raise serializers.ValidationError("Job role cannot be empty")
        return value

class JobCardSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        fields = [
            "id",
            "job_role",
            "department",
            "total_vacancies",
            "experience",
            "location",
            "package",
        ]

   


class JobDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        fields = [
            "id",
            "job_role",
            "location",
            "package",
            "total_vacancies",
            "experience",
            "job_description",
            "skills_required",
            "eligibility",
        ]

   