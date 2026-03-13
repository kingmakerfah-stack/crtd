from django.shortcuts import render
from .serializers import *
from .models import *
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsStudent
from rest_framework.exceptions import ValidationError
from drf_yasg.utils import swagger_auto_schema

# user id to student root model.
def student_id(id):
    return Student.objects.get(user=id) 

class StudentDataView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    @swagger_auto_schema(
    responses={
        200: "Student profile retrieved successfully.",
        401: "Authentication credentials were not provided.",
        403: "User is not authorized as a student."
    },
    operation_description="Returns complete student profile including personal details, education, and career preference."
    )
    def get(self, request):
        student = student_id(request.user.id)  # Cleanest way

        personal_detail = getattr(student, "personal_detail", None)
        education = getattr(student, "education", None)
        career_preference = getattr(student, "career_preference", None)

        data = {
            "personal_detail": StudentPersonalDetailSerializer(personal_detail).data if personal_detail else None,
            "education": StudentEducationSerializer(education).data if education else None,
            "career_preference": StudentCareerPreferenceSerializer(career_preference).data if career_preference else None,
        }

        return Response(data, status=status.HTTP_200_OK)
    
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from accounts.permissions import IsStudent


class StudentPersonalDetails(APIView):
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get_object(self, request):
        student = request.user.student_profile
        try:
            return student.personal_detail
        except StudentPersonalDetail.DoesNotExist:
            raise NotFound("Personal details not found.")

    @swagger_auto_schema(
        request_body=StudentPersonalDetailSerializer,
        responses={
            200: StudentPersonalDetailSerializer,
            400: "Validation Error",
            404: "Personal details not found."
        },
        operation_description="""
        Fully update the authenticated student's personal details.
        This endpoint replaces the entire personal profile with the data provided in the request body.
        Fields not included in the request may be set to null depending on serializer configuration.
        
        Frontend should send the complete object when performing a PUT request.
        """
    )
    # 🔵 FULL UPDATE
    def put(self, request):
        personal_detail = self.get_object(request)

        serializer = StudentPersonalDetailSerializer(
            personal_detail,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    # 🟢 PARTIAL UPDATE

    @swagger_auto_schema(
        request_body=StudentPersonalDetailSerializer,
        responses={
            200: StudentPersonalDetailSerializer,
            400: "Validation Error",
            404: "Personal details not found."
        },
        operation_description="""
        Partially update the authenticated student's personal details.
        This endpoint updates only the fields provided in the request body for the student's personal details.
        Fields not included in the request will remain unchanged.

        Frontend should send only the fields that need to be updated when performing a PATCH request.
        """
        )
    def patch(self, request):
        personal_detail = self.get_object(request)

        serializer = StudentPersonalDetailSerializer(
            personal_detail,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    


class StudentEducationView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get_object(self, request):
        student = request.user.student_profile
        try:
            return student.education
        except StudentEducation.DoesNotExist:
            raise NotFound("Education details not found.")
        
    @swagger_auto_schema(
    request_body=StudentEducationSerializer,
    responses={
        200: StudentEducationSerializer,
        400: "Validation Error",
        404: "Education details not found."
    },
    operation_description="""
    Fully update the authenticated student's education details.
    This endpoint replaces the entire education record with the data provided in the request body.
    Fields not included in the request may be set to null depending on serializer configuration.

    Frontend should send the complete object when performing a PUT request.
    """
    )
    def put(self, request):
        education = self.get_object(request)

        serializer = StudentEducationSerializer(
            education,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
    request_body=StudentEducationSerializer,
    responses={
        200: StudentEducationSerializer,
        400: "Validation Error",
        404: "Education details not found."
    },
    operation_description="""
    Partially update the authenticated student's education details.
    This endpoint updates only the fields provided in the request body for the student's education record.
    Fields not included in the request will remain unchanged.

    Frontend should send only the fields that need to be updated when performing a PATCH request.
    """
    )
    def patch(self, request):
        education = self.get_object(request)

        serializer = StudentEducationSerializer(
            education,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class StudentCareerPreferenceView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get_object(self, request):
        student = request.user.student_profile
        try:
            return student.career_preference
        except StudentCareerPreference.DoesNotExist:
            raise NotFound("Career preference not found.")
        
    @swagger_auto_schema(
    request_body=StudentCareerPreferenceSerializer,
    responses={
        200: StudentCareerPreferenceSerializer,
        400: "Validation Error",
        404: "Career preference not found."
    },
    operation_description="""
    Fully update the authenticated student's career preference details.
    This endpoint replaces the entire career preference record with the data provided in the request body.
    Fields not included in the request may be set to null depending on serializer configuration.

    Frontend should send the complete object when performing a PUT request.
    """
    )
    def put(self, request):
        career = self.get_object(request)

        serializer = StudentCareerPreferenceSerializer(
            career,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
    request_body=StudentCareerPreferenceSerializer,
    responses={
        200: StudentCareerPreferenceSerializer,
        400: "Validation Error",
        404: "Career preference not found."
    },
    operation_description="""
    Partially update the authenticated student's career preference details.
    This endpoint updates only the fields provided in the request body for the student's education record.
    Fields not included in the request will remain unchanged.

    Frontend should send only the fields that need to be updated when performing a PATCH request.
    """
    )
    def patch(self, request):
        career = self.get_object(request)

        serializer = StudentCareerPreferenceSerializer(
            career,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)