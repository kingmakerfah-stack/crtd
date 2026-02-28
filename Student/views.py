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
    return Student.objects.get(User=id) 


class StudentPersonalDetails(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def get(self, request):
        student = request.user.student_profile

        try:
            personal_detail = student.personal_detail
        except StudentPersonalDetail.DoesNotExist:
            return Response(
                {"detail": "Personal details not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = StudentPersonalDetailSerializer(personal_detail)
        return Response(serializer.data)

    def post(self, request):
        student = request.user.student_profile

        # Prevent duplicate
        if hasattr(student, "personal_detail"):
            raise ValidationError("Personal detail already exists.")

        serializer = StudentPersonalDetailSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(student=student)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
