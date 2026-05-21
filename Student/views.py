from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from django.conf import settings
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from accounts.permissions import IsStudent, IsActiveSubscriber
from applications.models import Application, CoolDown
from applications.serializers import ApplyJobSerializer, StudentApplicationSerializer
from jobs.models import Job
from jobs.serializers import JobCardSerializer
from payments.models import StudentPayment
from payments.services import create_razorpay_order
from payments.student_subscription_service import build_subscription_summary, has_active_subscription
from subscription.models import SubscriptionPlan
from .serializers import *
from .models import *
from .utils import update_profile_status

# ✅ FIX: Removed all duplicate imports that were scattered mid-file
# ✅ FIX: Removed unused student_id() helper — all views now use request.user.student_profile consistently


STUDENT_PAYMENT_INITIATE_RESPONSE_EXAMPLE = {
    "order_id": "order_RZP_123456789",
    "amount": 200000,
    "key": "rzp_live_public_key",
}

STUDENT_SUBSCRIPTION_STATUS_EXAMPLE = {
    "is_paid": True,
    "status": "ACTIVE",
    "registration_number": "CRTD2026000001",
    "payment_date": "2026-04-13",
    "expiry_date": "2026-10-13",
    "days_remaining": 183,
}

STUDENT_JOBS_LIST_EXAMPLE = {
    "subscription": {
        "is_paid": False,
        "status": None,
        "registration_number": None,
        "payment_date": None,
        "expiry_date": None,
        "days_remaining": 0,
        "lock_message": "Payment required to apply for jobs.",
    },
    "jobs": [
        {
            "id": 1,
            "job_role": "Backend Developer",
            "job_mode": "Remote",
            "department": "Engineering",
            "total_vacancies": 2,
            "experience": "2 years",
            "location": "Remote",
            "package": "Standard",
        }
    ],
}

STUDENT_JOB_APPLY_SUCCESS_EXAMPLE = {
    "message": "Application submitted successfully",
}

STUDENT_JOB_APPLY_COOLDOWN_EXAMPLE = {
    "message": "Application limit reached",
    "days_left": 7,
}


# ---------------------------------------------------------
# Helper: safely fetch Student from request
# ---------------------------------------------------------
def get_student(request):
    """
    Safely fetches the Student profile linked to the authenticated user.
    Raises NotFound if no student profile exists.
    """
    try:
        return request.user.student_profile
    except Student.DoesNotExist:
        raise NotFound("Student profile not found.")


# ---------------------------------------------------------
# Student Full Profile View (GET only)
# ---------------------------------------------------------

class StudentDataView(APIView):
    permission_classes = [IsStudent]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        responses={
            200: "Student profile retrieved successfully.",
            401: "Authentication credentials were not provided.",
            403: "User is not authorized as a student.",
            404: "Student profile not found.",
        },
        tags=["Student"],
        operation_description="Returns complete student profile including personal details, education, and career preference."
    )
    def get(self, request):
        try:
            student = request.user.student_profile
        except Exception:
            raise NotFound("Student profile not found.")

        data = {
            "personal_detail": StudentPersonalDetailSerializer(
                getattr(student, "personal_detail", None)
            ).data if hasattr(student, "personal_detail") else None,

            "education": StudentEducationSerializer(
                getattr(student, "education", None)
            ).data if hasattr(student, "education") else None,

            "career_preference": StudentCareerPreferenceSerializer(
                getattr(student, "career_preference", None)
            ).data if hasattr(student, "career_preference") else None,
        }

        return Response(data, status=status.HTTP_200_OK)

# ---------------------------------------------------------
# Student Personal Details (POST, PUT, PATCH)
# ---------------------------------------------------------
class StudentPersonalDetails(APIView):
    permission_classes = [IsStudent]

    def get_object(self, request):
        # ✅ FIX: Guarded both student_profile and personal_detail access
        student = get_student(request)
        try:
            return student.personal_detail
        except StudentPersonalDetail.DoesNotExist:
            raise NotFound("Personal details not found.")

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentPersonalDetailSerializer,
        responses={
            201: StudentPersonalDetailSerializer,
            400: "Validation Error",
            409: "Personal details already exist.",
        },
        tags=["Student"],
        operation_description="Create personal details for the authenticated student."
    )
    # ✅ FIX: Added POST endpoint so serializer create() is actually reachable
    def post(self, request):
        student = get_student(request)
        serializer = StudentPersonalDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


    # 🟢 PARTIAL UPDATE
    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentPersonalDetailSerializer,
        responses={
            200: StudentPersonalDetailSerializer,
            400: "Validation Error",
            404: "Personal details not found.",
        },
        tags=["Student"],
        operation_description=(
            "Fully update the authenticated student's personal details. "
            "Frontend should send the complete object when performing a PUT request."
        )
    )
    def put(self, request):
        personal_detail = self.get_object(request)
        serializer = StudentPersonalDetailSerializer(personal_detail, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(personal_detail.student)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentPersonalDetailSerializer,
        responses={
            200: StudentPersonalDetailSerializer,
            400: "Validation Error",
            404: "Personal details not found.",
        },
        tags=["Student"],
        operation_description=(
            "Partially update the authenticated student's personal details. "
            "Frontend should send only the fields that need to be updated."
        )
    )
    def patch(self, request):
        personal_detail = self.get_object(request)
        serializer = StudentPersonalDetailSerializer(personal_detail, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(personal_detail.student)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------
# Student Education (POST, PUT, PATCH)
# ---------------------------------------------------------
class StudentEducationView(APIView):
    permission_classes = [IsStudent]

    def get_object(self, request):
        # ✅ FIX: Guarded both student_profile and education access
        student = get_student(request)
        try:
            return student.education
        except StudentEducation.DoesNotExist:
            raise NotFound("Education details not found.")

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentEducationSerializer,
        responses={
            201: StudentEducationSerializer,
            400: "Validation Error",
            409: "Education record already exists.",
        },
        tags=["Student"],
        operation_description="Create education details for the authenticated student."
    )
    # ✅ FIX: Added POST endpoint so serializer create() is actually reachable
    def post(self, request):
        student = get_student(request)
        serializer = StudentEducationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(student=student)  # student injected server-side
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentEducationSerializer,
        responses={
            200: StudentEducationSerializer,
            400: "Validation Error",
            404: "Education details not found.",
        },
        tags=["Student"],
        operation_description=(
            "Fully update the authenticated student's education details. "
            "Frontend should send the complete object when performing a PUT request."
        )
    )
    def put(self, request):
        education = self.get_object(request)
        serializer = StudentEducationSerializer(education, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(education.student)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentEducationSerializer,
        responses={
            200: StudentEducationSerializer,
            400: "Validation Error",
            404: "Education details not found.",
        },
        tags=["Student"],
        operation_description=(
            "Partially update the authenticated student's education details. "
            "Frontend should send only the fields that need to be updated."
        )
    )
    def patch(self, request):
        education = self.get_object(request)
        serializer = StudentEducationSerializer(education, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(education.student)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------
# Student Career Preference (POST, PUT, PATCH)
# ---------------------------------------------------------
class StudentCareerPreferenceView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get_object(self, request):
        # ✅ FIX: Guarded both student_profile and career_preference access
        student = get_student(request)
        try:
            return student.career_preference
        except StudentCareerPreference.DoesNotExist:
            raise NotFound("Career preference not found.")

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentCareerPreferenceSerializer,
        responses={
            201: StudentCareerPreferenceSerializer,
            400: "Validation Error",
            409: "Career preference already exists.",
        },
        tags=["Student"],
        operation_description="Create career preference for the authenticated student."
    )
    # ✅ FIX: Added POST endpoint so serializer create() is actually reachable
    def post(self, request):
        student = get_student(request)
        serializer = StudentCareerPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(student=student)  # student injected server-side
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentCareerPreferenceSerializer,
        responses={
            200: StudentCareerPreferenceSerializer,
            400: "Validation Error",
            404: "Career preference not found.",
        },
        tags=["Student"],
        operation_description=(
            "Fully update the authenticated student's career preference details. "
            "Frontend should send the complete object when performing a PUT request."
        )
    )
    def put(self, request):
        career = self.get_object(request)
        serializer = StudentCareerPreferenceSerializer(career, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(career.student)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        request_body=StudentCareerPreferenceSerializer,
        responses={
            200: StudentCareerPreferenceSerializer,
            400: "Validation Error",
            404: "Career preference not found.",
        },
        tags=["Student"],
        operation_description=(
            "Partially update the authenticated student's career preference details. "
            "Frontend should send only the fields that need to be updated."
        )
    )
    def patch(self, request):
        career = self.get_object(request)
        serializer = StudentCareerPreferenceSerializer(career, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_profile_status(career.student)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentPaymentInitiateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Student Payments"],
        responses={
            201: openapi.Response(
                description="Payment order created successfully.",
                examples={"application/json": STUDENT_PAYMENT_INITIATE_RESPONSE_EXAMPLE},
            ),
            400: "Profile incomplete or active subscription exists.",
            401: "Authentication credentials were not provided.",
            403: "Student role required.",
            404: "Subscription plan not found.",
        },
        operation_description=(
            "Initiate student subscription payment by creating Razorpay order and a StudentPayment record. "
            "No subscription activation occurs here; webhook confirmation is mandatory."
        ),
    )
    def post(self, request):
        student = get_student(request)
        if not student.profile_completed:
            return Response({"error": "Complete profile first"}, status=status.HTTP_400_BAD_REQUEST)

        if has_active_subscription(request.user):
            return Response({"error": "Active subscription already exists"}, status=status.HTTP_400_BAD_REQUEST)

        amount = int(getattr(settings, "SUBSCRIPTION_AMOUNT_PAISE", 0) or 0)
        if amount <= 0:
            plan = SubscriptionPlan.objects.filter(is_active=True).first()
            if not plan:
                return Response({"error": "Subscription plan not found."}, status=status.HTTP_404_NOT_FOUND)
            amount = int(plan.final_price * 100)

        order = create_razorpay_order(request.user.id, amount)
        StudentPayment.objects.create(
            student=request.user,
            razorpay_order_id=order["id"],
            amount=amount,
            status=StudentPayment.STATUS_CREATED,
        )

        return Response(
            {
                "order_id": order["id"],
                "amount": amount,
                "key": settings.RAZORPAY_KEY_ID,
            },
            status=status.HTTP_201_CREATED,
        )


class StudentSubscriptionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Student Payments"],
        responses={
            200: openapi.Response(
                description="Current subscription summary for authenticated student.",
                examples={"application/json": STUDENT_SUBSCRIPTION_STATUS_EXAMPLE},
            ),
            401: "Authentication credentials were not provided.",
            403: "Student role required.",
        },
        operation_description="Return current payment/subscription status used by frontend for gating.",
    )
    def get(self, request):
        return Response(build_subscription_summary(request.user), status=status.HTTP_200_OK)


class StudentJobListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Student Jobs"],
        responses={
            200: openapi.Response(
                description="List all jobs plus current subscription summary.",
                examples={"application/json": STUDENT_JOBS_LIST_EXAMPLE},
            ),
            401: "Authentication credentials were not provided.",
            403: "Student role required.",
        },
        operation_description=(
            "Retrieve all available jobs for authenticated students. "
            "Response includes subscription summary and lock message for frontend button state control."
        ),
    )
    def get(self, request):
        jobs = Job.objects.all().order_by("-id")
        serializer = JobCardSerializer(jobs, many=True)

        subscription = build_subscription_summary(request.user)
        lock_message = None
        if not subscription["is_paid"]:
            lock_message = "Payment required to apply for jobs."

        return Response(
            {
                "subscription": {**subscription, "lock_message": lock_message},
                "jobs": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class StudentJobApplyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudent, IsActiveSubscriber]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Student Jobs"],
        manual_parameters=[
            openapi.Parameter(
                "job_id",
                openapi.IN_PATH,
                description="Job primary key",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={
            201: openapi.Response(
                description="Application submitted successfully.",
                examples={"application/json": STUDENT_JOB_APPLY_SUCCESS_EXAMPLE},
            ),
            400: openapi.Response(
                description="Profile incomplete, duplicate apply, or cooldown active.",
                examples={"application/json": STUDENT_JOB_APPLY_COOLDOWN_EXAMPLE},
            ),
            401: "Authentication credentials were not provided.",
            403: "Active subscription required.",
            404: "Job not found.",
        },
        operation_description=(
            "Apply to a specific job with active-subscription enforcement, profile-completion check, "
            "duplicate prevention, and cooldown restrictions."
        ),
    )
    def post(self, request, job_id):
        student = get_student(request)
        if not student.profile_completed:
            return Response(
                {"message": "Please complete your profile before applying"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise NotFound("Job not found")

        cooldown_obj, _ = CoolDown.objects.get_or_create(id=1, defaults={"cooldown_days": 0})
        admin_cooldown_days = cooldown_obj.cooldown_days
        last_application = Application.objects.filter(student=student).order_by("-applied_at").first()

        if last_application:
            today = timezone.now().date()
            applied_date = last_application.applied_at.date()
            last_cooldown_days = last_application.cooldown_days_used
            diff_days = (today - applied_date).days

            if diff_days < last_cooldown_days:
                remaining_days = last_cooldown_days - diff_days
                return Response(
                    {
                        "message": "Application limit reached",
                        "days_left": remaining_days,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = ApplyJobSerializer(data={}, context={"request": request, "job": job})
        serializer.is_valid(raise_exception=True)
        serializer.save(cooldown_days_used=admin_cooldown_days)
        return Response({"message": "Application submitted successfully"}, status=status.HTTP_201_CREATED)


class StudentApplicationHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStudent, IsActiveSubscriber]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Student Applications"],
        responses={
            200: openapi.Response(
                description="Application history of authenticated student.",
                schema=StudentApplicationSerializer(many=True),
            ),
            401: "Authentication credentials were not provided.",
            403: "Active subscription required.",
        },
        operation_description="Return only authenticated student's application history.",
    )
    def get(self, request):
        student = get_student(request)
        applications = Application.objects.filter(student=student).select_related("job")
        serializer = StudentApplicationSerializer(applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

