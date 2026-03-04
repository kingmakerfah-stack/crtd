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


# ---------------------------------------------------------
# STUDENT OTP VERIFICATION VIEWS
# ---------------------------------------------------------

class StudentOTPRequestView(APIView):
    """
    Endpoint to request OTP for student email verification.
    
    This is called after student registration to send OTP for email verification.
    
    Accepts:
    - enrollment_id: The student's enrollment ID
    
    Returns:
    - Success message if OTP was sent
    """
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        from utils.email_service import EmailService, generate_otp
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {"error": "Student profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate OTP
        otp_code = generate_otp()
        
        # Create or update StudentOTP
        student_otp, created = StudentOTP.objects.update_or_create(
            student=student,
            defaults={
                'otp': otp_code,
                'expires_at': timezone.now() + timedelta(minutes=10),
                'is_verified': False
            }
        )
        
        # Send OTP email
        context = {
            'first_name': student.user.email.split('@')[0],
            'current_year': timezone.now().year
        }
        EmailService.send_otp_email(student.user.email, otp_code, context)
        
        return Response(
            {
                "message": "OTP sent to your registered email address.",
                "email": student.user.email
            },
            status=status.HTTP_200_OK
        )


class StudentOTPVerificationView(APIView):
    """
    Endpoint to verify OTP code for student registration.
    
    Accepts:
    - enrollment_id: The student's enrollment ID
    - otp: The OTP code (4 digits)
    
    Returns:
    - Success message if OTP is valid
    - Error message if OTP is invalid, expired, or doesn't match
    """
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        serializer = StudentOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        enrollment_id = serializer.validated_data['enrollment_id']
        otp_code = serializer.validated_data['otp']
        
        # Get student
        try:
            student = Student.objects.get(enrollment_id=enrollment_id)
        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found with this enrollment ID."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get StudentOTP
        try:
            student_otp = StudentOTP.objects.get(student=student)
        except StudentOTP.DoesNotExist:
            return Response(
                {"error": "No OTP found for this student. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if expired
        if student_otp.is_expired():
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already verified
        if student_otp.is_verified:
            return Response(
                {"error": "OTP has already been used."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if OTP matches
        if student_otp.otp != otp_code:
            return Response(
                {"error": "Invalid OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as verified
        student_otp.is_verified = True
        student_otp.save()
        
        # Update user's email_verified status
        user = student.user
        user.email_verified = True
        user.save()
        
        return Response(
            {
                "message": "Email verified successfully!",
                "enrollment_id": student.enrollment_id,
                "email": user.email
            },
            status=status.HTTP_200_OK
        )