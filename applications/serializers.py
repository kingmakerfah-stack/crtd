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