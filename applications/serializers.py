from rest_framework import serializers
from .models import Application,CoolDown


class ApplyJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['id']

    def validate(self,data):
        user = self.context['request'].user
        job = self.context['job']

        student = getattr(user,"student_profile",None)
        if not student:
            raise serializers.ValidationError("Student profile not found.")
        
        if Application.objects.filter(student=student,job=job).exists():
            raise serializers.ValidationError("You have already applied to this job")
        return data
    
    def create(self,validated_data):
        user=self.context['request'].user
        job = self.context['job']
        student = getattr(user, "student_profile", None)

        return Application.objects.create(
            student=student,
            job=job,
            cooldown_days_used=validated_data.get('cooldown_days_used')
        )


class CoolDownSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoolDown
        fields = "__all__"

    def validate_cooldown_days(self,value):
        if value is None:
            raise serializers.ValidationError("Cooldown days is required.")
        if value < 0:
            raise serializers.ValidationError("Cooldown days can not be negative.")
        return value


class JobWiseSummarySerializer(serializers.Serializer):
    job_id = serializers.IntegerField(source="job__id")
    profile = serializers.CharField(source="job__job_role")
    total_applications = serializers.IntegerField()
    interview_done = serializers.IntegerField()
    pending_interview = serializers.IntegerField()
    
class JobApplicationsSerializer(serializers.ModelSerializer):

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    interview_status = serializers.CharField(source="status")
    cooling_period = serializers.IntegerField(source="cooldown_days_used")

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "email",
            "contact",
            "interview_status",
            "cooling_period",
        ]

    def get_name(self, obj):
        pd = getattr(obj.student, "personal_detail", None)
        return f"{pd.first_name} {pd.last_name}" if pd else None

    def get_email(self, obj):
        pd = getattr(obj.student, "personal_detail", None)
        return pd.email if pd else None

    def get_contact(self, obj):
        pd = getattr(obj.student, "personal_detail", None)
        return pd.whatsapp_no if pd else None

class ApplicationDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    applied_at = serializers.DateTimeField(format="%d-%m-%Y")

    class Meta:
        model = Application
        fields = [
            "id",
            "name",
            "email",
            "job_title",
            "applied_at",
            "experience",
            "skills",
            "status",
        ]

    def get_name(self, obj):
        pd = getattr(obj.student, "personal_detail", None)
        return f"{pd.first_name} {pd.last_name}" if pd else None

    def get_email(self, obj):
        pd = getattr(obj.student, "personal_detail", None)
        return pd.email if pd else None

    def get_job_title(self, obj):
        return obj.job.job_role if obj.job else None

    def get_experience(self, obj):
        cp = getattr(obj.student, "career_preference", None)
        return cp.experience if cp else None

    def get_skills(self, obj):
        cp = getattr(obj.student, "education", None)
        return cp.skills if cp else []


class ApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["status"]
    def validate_status(self, value):
        value = value.lower() 

        valid_choices = [choice[0] for choice in Application.STATUS_CHOICES]

        if value not in valid_choices:
            raise serializers.ValidationError("Invalid status value")

        return value

class StudentApplicationSerializer(serializers.ModelSerializer):
    job_role = serializers.CharField(source="job.job_role")
    submitted_date = serializers.DateTimeField(source="applied_at",format="%d %b %Y")

    class Meta:
        model = Application
        fields = [
            "id",
            "job_role",
            "reference_id",
            "submitted_date",
            "status"
        ]

class UpdateCoolDownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["cooldown_days_used","reason"]

        def validate_cooldown_days_used(self,value):
            if value < 0:
                raise serializers.ValidationError("Cooldown cannot be negative")
            return value