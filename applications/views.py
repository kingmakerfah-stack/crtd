from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from .models import Application,CoolDown
from jobs.models import Job
from django.db.models import Count,Q
from drf_yasg.utils import swagger_auto_schema                                              
from accounts.access_control import filter_applications_for_user
from accounts.permissions import HasModuleAccess, IsAdminPortalUser
from .paginations import ApplicationPagination
from .serializers import (ApplyJobSerializer,CoolDownSerializer,
                        StudentApplicationSerializer,
                        JobApplicationsSerializer,
                        JobWiseSummarySerializer,
                        ApplicationStatusUpdateSerializer,
                        UpdateCoolDownSerializer,
                        ApplicationDetailSerializer
                          )
from accounts.permissions import IsActiveSubscriber

class ApplyJobView(APIView):
    permission_classes = [IsAuthenticated,IsActiveSubscriber]

    @swagger_auto_schema(
            tags=["Applications"],
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

        if student and not student.profile_completed:
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
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'edit'
    @swagger_auto_schema(
            tags=["Applications"],
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
    
# dashboard job summary
class RealTimeActivitySummaryView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'view'

    @swagger_auto_schema(
    responses={
        200: "Dashboard summary fetched successfully",
        401: "Unauthorized",
        403: "Permission Denied"
    },
    tags=["Applications"],
    operation_description="""
    Get real-time job application summary for job application dashboard.
    
    Returns total applications, pending interviews, completed interviews,
    and current cooldown period in days.
    """
    )
    def get(self, request):
        scoped_applications = filter_applications_for_user(request.user, Application.objects.all())
        data = scoped_applications.aggregate(
            total_job_applied=Count("id"),
            interviews_pending=Count("id", filter=Q(status="pending")),
            interviews_completed=Count("id", filter=Q(status="selected")),
        )

        cooling_period = CoolDown.objects.filter(id=1).first()

        data["cooling_period"] = cooling_period.cooldown_days if cooling_period else 0

        return Response(data,status=status.HTTP_200_OK)

#role wise jobs view
class JobWiseSummaryView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'view'

    @swagger_auto_schema(
    responses={
        200: "Job-wise summary fetched successfully",
        401: "Unauthorized",
        403: "Permission Denied"
    },
    tags=["Applications"],
    operation_description="""
    Get job role-wise application summary for job application dashboard.

    Returns number of applications for each job role (e.g., Frontend, Backend),
    including total applications, interviews completed, and interviews pending.
    """
    )
    def get(self, request):
        queryset = filter_applications_for_user(request.user, Application.objects.all()).values(
            'job__id',
            'job__job_role'
        ).annotate(
            total_applications=Count('id'),
            interview_done=Count('id', filter=Q(status='selected')),
            pending_interview=Count('id', filter=Q(status='pending'))
        )

        serializer = JobWiseSummarySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class JobApplicationsView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'view'
    @swagger_auto_schema(
    responses={
        200: "Job applications fetched successfully",
        401: "Unauthorized",
        403: "Permission Denied",
        404: "Job not found"
    },
    tags=["Applications"],
    operation_description="""
        Get all applications for a specific job.

        Returns list of students who applied for the given job (e.g., Frontend),
        including their details. Data is paginated.
        """
    )
    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise NotFound("Job not found.")

        applications = filter_applications_for_user(request.user, Application.objects.filter(
            job=job
        )).select_related(
            'job',
            'student__personal_detail',
            'student__career_preference',
            'student__education'
        )

        paginator = ApplicationPagination()

        page = paginator.paginate_queryset(applications, request)
        serializer = JobApplicationsSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class ApplicationDetailView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'view'
    @swagger_auto_schema(
    responses={
        200: "Application detail fetched successfully",
        401: "Unauthorized",
        403: "Permission Denied",
        404: "Application not found"
    },
    tags=["Applications"],
    operation_description="""
        Get application details by ID.

        Used when admin clicks on edit/view button to open a single application.
        Returns complete details of the selected application.
        """
    )
    def get(self, request,id):
        try:
            application = filter_applications_for_user(request.user, Application.objects.all()).get(id=id)
        except Application.DoesNotExist:
            return Response(
                {"message": "Application not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ApplicationDetailSerializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
            
#update interview status view
class UpdateApplicationStatusView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'edit'

    @swagger_auto_schema(
        request_body=ApplicationStatusUpdateSerializer,  
        responses={200: "Status updated successfully"},
        tags=["Applications"]
    )
    def patch(self,request,id):
        try:
            application = filter_applications_for_user(request.user, Application.objects.all()).get(id=id)
        except Application.DoesNotExist:
            raise NotFound("Application not found.")
        serializer = ApplicationStatusUpdateSerializer(application,data=request.data,partial=True)  
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message":"Status updated successfully."},
                        status=status.HTTP_200_OK)


#student my application view
class StudentApplicationListView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
            tags=["Applications"]
    )
    def get(self, request):
        student = getattr(request.user, "student_profile", None)

        if not student:
            return Response({"error": "Student not found"}, status=404)
        
        applications = Application.objects.filter(
            student=student
        ).select_related('job')

        serializer = StudentApplicationSerializer(applications, many=True)
        return Response(serializer.data)

class UpdateStudentCoolDownView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'job_applications'
    required_module_action = 'edit'
    @swagger_auto_schema(
    request_body=UpdateCoolDownSerializer,
    responses={
        200: "Cooldown updated successfully",
        400: "Invalid data",
        404: "Application not found"
    },
    tags=["Applications"],
    operation_description="""
        Update application cooldown period.

        Used by admin to modify cooldown days for a specific application.
        """
    )
    def patch(self,request,id):
        try:
            application = filter_applications_for_user(request.user, Application.objects.all()).get(id=id)
        except Application.DoesNotExist:
            raise NotFound("Application Not found.")
        
        serializer=UpdateCoolDownSerializer(application,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message":"Cooldown days updated Successfully"},
                        status=status.HTTP_200_OK)
