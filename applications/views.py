from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated,AllowAny
from .models import Application,CoolDown
from .serializers import ApplyJobSerializer,CoolDownSerializer
from jobs.models import Job

from drf_yasg.utils import swagger_auto_schema

class ApplyJobView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
              responses={
            201: "Application submitted successfully",
            400: "Profile incomplete or cooldown active",
            404: "Job not found"
    },
        operation_description ="""
        Apply for a job with cooldown restriction.
        User must complete profile before applying.
        After each application, a cooldown period is applied.
        If user applies before cooldown ends, remaining days will be returned."""
        )
    
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

class CoolDownUpdateView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(
            request_body = CoolDownSerializer,
            responses={
            200: "Cooldown days updated successfully",
            400: "Validation Error"
            },
            operation_description=
                "This API allows admin to set the cooldown period (in days) between job applications."
    )
    def put(self,request):
        cooldown_days,_=CoolDown.objects.get_or_create(id=1,defaults={"cooldown_days":0})

        serializer=CoolDownSerializer(cooldown_days,data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message":"Cooldown days updated Successfully"},
                        status=status.HTTP_200_OK)