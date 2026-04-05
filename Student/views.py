from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from drf_yasg.utils import swagger_auto_schema

from accounts.permissions import IsStudent
from .serializers import *
from .models import *
from .utils import update_profile_status

# ✅ FIX: Removed all duplicate imports that were scattered mid-file
# ✅ FIX: Removed unused student_id() helper — all views now use request.user.student_profile consistently


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

