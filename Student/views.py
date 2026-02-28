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

# user id to student root model.
def student_id(id):
    return Student.objects.get(user=id) 

class StudentDataView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

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

    def put(self, request):
        education = self.get_object(request)

        serializer = StudentEducationSerializer(
            education,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

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

    def put(self, request):
        career = self.get_object(request)

        serializer = StudentCareerPreferenceSerializer(
            career,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

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