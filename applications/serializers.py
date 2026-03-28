from rest_framework import serializers
from .models import Application


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
