from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from .models import Application,CoolDown
from .serializers import ApplyJobSerializer
from jobs.models import Job
from drf_yasg.utils import swagger_auto_schema

class ApplyJobView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        user = request.user
        student = getattr(user, "student_profile", None)

        if student and not student.is_profile_complete:
            return Response({
                "message": "Please complete your profile before applying"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = Job.objects.get(id=id)
        except Job.DoesNotExist:
            raise NotFound("Job not found")
        
        cooldown_obj,_ = CoolDown.objects.get_or_create(id=1,defaults={"cooldown_days":0})
        admin_cooldown_days=cooldown_obj.cooldown_days
        last_application = Application.objects.filter(student=student).order_by('-applied_at').first()

        if last_application:
            today = timezone.now().date()
            applied_date = last_application.applied_at.date()
            last_cooldown_days=last_application.cooldown_days_used

            diff_days = (today - applied_date).days

            if diff_days <last_cooldown_days :
                remaining_days = last_cooldown_days - diff_days

                return Response({
                    "message": "Application limit reached",
                    "days_left": remaining_days
                }, status=status.HTTP_400_BAD_REQUEST)
        serializer = ApplyJobSerializer(
            data={},
            context={'request': request, 'job': job}
        )

        if serializer.is_valid():
            serializer.save(cooldown_days_used=admin_cooldown_days)
            return Response({
                "message": "Application submitted successfully"
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)