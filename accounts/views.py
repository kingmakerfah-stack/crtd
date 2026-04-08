from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .serializers import RoleBasedRegisterSerializer as RegisterSerializer
from .serializers import GoogleAuthSerializer
from .serializers import (
    OTPRequestSerializer,
    OTPVerificationSerializer,
    PasswordResetSerializer,
    ChangePasswordSerializer,
    UserLoginSerializer,
    RBACLoginSerializer,
    RBACOTPVerifySerializer,
    MeSerializer,
    ModuleSerializer,
    CreateSubAdminSerializer,
    UpdateSubAdminModulesSerializer,
    UpdateSubAdminRoleSerializer,
    SubAdminListSerializer,
)
from drf_yasg.utils import swagger_auto_schema
User = get_user_model()
from pre_application.models import ReferalCode , PreApplication
from rest_framework.generics import get_object_or_404
from Student.models import Student, StudentPersonalDetail, StudentEducation, StudentCareerPreference
from .models import Module, SubAdminProfile
from .pagination import AccountsListPagination
from .permissions import IsSuperAdmin, IsAdminPortalUser, CanManageSubadmins
from .utils import (
    clear_user_invalidation,
    clear_user_me_cache,
    get_cached_me,
    get_tokens_for_user,
    invalidate_user_session,
    set_cached_me,
)

from utils.email_service import EmailService


def _is_superadmin(user):
    return getattr(user, "role", None) == "superadmin"


def _manageable_subadmin_users(actor):
    queryset = User.objects.filter(role='subadmin').order_by('-created_at', '-id')
    if _is_superadmin(actor):
        return queryset
    return queryset.filter(subadmin_profile__created_by=actor)


def _manageable_subadmin_profiles(actor):
    queryset = SubAdminProfile.objects.all()
    if _is_superadmin(actor):
        return queryset.filter(user__role='subadmin')
    return queryset.filter(user__role='subadmin', created_by=actor)


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=GoogleAuthSerializer,
        responses={
            200: "Login successful.",
            400: "Invalid Google token or role mismatch.",
            500: "Google OAuth client ID is not configured."
        },
        tags=["Accounts"],
        operation_description="Authenticate user using Google ID token."
    )
    @transaction.atomic
    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["id_token"]
        role = serializer.validated_data.get("role")
        referral_code = serializer.validated_data.get("referral_code")
        referral = None
        pre_app = None

        if not settings.GOOGLE_OAUTH_CLIENT_ID:
            return Response(
                {"detail": "Google OAuth client ID is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            id_info = google_id_token.verify_oauth2_token(
                token_value,
                google_requests.Request(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid Google ID token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = id_info.get("email")
        email_verified = id_info.get("email_verified", False)

        if not email or not email_verified:
            return Response(
                {"detail": "Google account email is not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email=email).first()

        # First-time Google signup must be tied to an existing pre-application.
        if not user and not referral_code:
            return Response(
                {"detail": "referral_code is required for first-time Google signup."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If a referral code is supplied, enforce that the Google email matches
        # the pre-application email and that the referral is still valid.
        if referral_code:
            referral = get_object_or_404(ReferalCode.objects.select_related("student"), code=referral_code)

            if referral.status != "not_used":
                return Response(
                    {"detail": "Referral code already used."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pre_app = referral.student
            if not pre_app.verified:
                return Response(
                    {"detail": "Pre-application not verified yet."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if pre_app.email.lower() != email.lower():
                return Response(
                    {"detail": "Use the same Google account as the referral email."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Force role to student for referral-based signup
            if role and role != "student":
                return Response(
                    {"detail": "Role must be student for referral signup."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            role = "student"

        if not user and not role:
            return Response(
                {"detail": "Role is required for first-time Google login."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user and role and user.role != role:
            return Response(
                {"detail": "Role does not match existing account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                if referral_code:
                    referral = get_object_or_404(
                        ReferalCode.objects.select_for_update().select_related("student"),
                        code=referral_code,
                    )
                    pre_app = referral.student

                    if pre_app.is_deleted:
                        return Response(
                            {"detail": "Referral code is linked to an archived pre-application."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if referral.status != ReferalCode.STATUS_NOT_USED or referral.is_used:
                        return Response(
                            {"detail": "Referral code already used."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if not pre_app.verified:
                        return Response(
                            {"detail": "Pre-application not verified yet."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                if not user:
                    user = User.objects.create_user(
                        email=email,
                        password=None,
                        role=role,
                    )
                    user.set_unusable_password()
                    user.email_verified = True
                    user.save(update_fields=["password", "email_verified"])

                if referral and pre_app:
                    student = getattr(user, "student_profile", None)
                    if not student:
                        student = Student.objects.create(
                            user=user,
                            enrollment_id=f"ENR-{pre_app.id}"
                        )

                        StudentPersonalDetail.objects.create(
                            student=student,
                            first_name=pre_app.first_name,
                            last_name=pre_app.last_name,
                            email=pre_app.email,
                            whatsapp_no=pre_app.whatsapp_no,
                            alternate_phone=pre_app.alternate_phone,
                            birthplace_state=pre_app.birthplace_state
                        )

                        StudentEducation.objects.create(
                            student=student,
                            qualification=pre_app.qualification,
                            specialization=pre_app.specialization,
                            college_name=pre_app.college_name,
                            college_state=pre_app.college_state,
                            passing_year=pre_app.passing_year
                        )

                        StudentCareerPreference.objects.create(
                            student=student,
                            preferred_time=pre_app.preferred_time
                        )

                    referral.status = ReferalCode.STATUS_ACCOUNT_CREATED
                    referral.is_used = True
                    referral.save(update_fields=["status", "is_used"])
        except IntegrityError:
            return Response(
                {"detail": "Could not complete Google signup. Please retry."},
                status=status.HTTP_409_CONFLICT,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )

# -------------------------------------------------------
# REGISTER VIEW
# -------------------------------------------------------
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: "Created",
            400: "Bad Request - invalid or missing reference code.",
        },
        tags=["Accounts"],
        operation_description=(
            "Register a student account after referral validation. "
            "Send reference_code from the referral validation API in the request body."
        ),
    )
    @transaction.atomic
    def post(self, request):
        # Accept both snake_case and camelCase from clients, then normalize.
        reference_code = request.data.get("reference_code") or request.data.get("referenceCode")

        if not reference_code:
            return Response(
                {"error": "reference_code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        referral = get_object_or_404(
            ReferalCode.objects.select_for_update().select_related("student"),
            code=reference_code,
        )

        # 2️⃣ Validate referral
        # Prefer status as source of truth; keep is_used fallback for compatibility.
        referral_already_used = (
            referral.status != ReferalCode.STATUS_NOT_USED
            or referral.is_used
        )
        if referral_already_used:
            return Response(
                {"error": "Referral code already used."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pre_app = referral.student

        if not pre_app.verified:
            return Response(
                {"error": "Pre-application not verified yet."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if pre_app.is_deleted:
            return Response(
                {"error": "Cannot register from an archived pre-application."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3️⃣ Register user
        data = {
            "email": request.data.get("email"),
            "password": request.data.get("password"),
            "confirm_password": request.data.get("confirm_password") or request.data.get("confirmPassword"),
            "reference_code": reference_code,
            "role": "student"
        }

        serializer = RegisterSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Prevent registration with a different email than approved in pre-application.
        if serializer.validated_data["email"].lower() != pre_app.email.lower():
            return Response(
                {"error": "Email must match the approved pre-application email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = serializer.save()

            student = Student.objects.create(
                user=user,
                enrollment_id=f"ENR-{pre_app.id}"
            )

            StudentPersonalDetail.objects.create(
                student=student,
                first_name=pre_app.first_name,
                last_name=pre_app.last_name,
                email=pre_app.email,
                whatsapp_no=pre_app.whatsapp_no,
                alternate_phone=pre_app.alternate_phone,
                birthplace_state=pre_app.birthplace_state
            )

            StudentEducation.objects.create(
                student=student,
                qualification=pre_app.qualification,
                specialization=pre_app.specialization,
                college_name=pre_app.college_name,
                college_state=pre_app.college_state,
                passing_year=pre_app.passing_year
            )

            StudentCareerPreference.objects.create(
                student=student,
                preferred_time=pre_app.preferred_time
            )

            referral.status = ReferalCode.STATUS_ACCOUNT_CREATED
            referral.is_used = True
            referral.save(update_fields=["status", "is_used"])
        except IntegrityError:
            transaction.set_rollback(True)
            return Response(
                {"error": "Registration could not be completed. Please retry."},
                status=status.HTTP_409_CONFLICT,
            )

        # With SQLite, creating the OTP record before this transaction  commits can
        # hit "database is locked". Queue the OTP workflow after commit instead.
        transaction.on_commit(
            lambda: EmailService.send_verification_otp(
                user,
                purpose='email_verification',
            )
        )

        return Response(
            {
                "message": "User registered successfully.",
                "email": user.email,
                "role": user.role
            },
            status=status.HTTP_201_CREATED
        )
# -------------------------------------------------------
# LOGIN VIEW (JWT TOKEN GENERATION)
# -------------------------------------------------------



class LoginView(APIView):
    """
    Handles user login.

    Accepts:
    - email
    - password

    If credentials are valid:
    - Generates JWT access and refresh tokens
    - Returns tokens + user role
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @swagger_auto_schema(
        request_body=UserLoginSerializer,
        responses={
            200: "Login successful.",
            401: "Invalid email or password.",
            403: "Email not verified.",
        },
        tags=["Accounts"],
        operation_description="Login user using email and password."
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        # Authenticate user
        user = authenticate(request, email=email, password=password)

        # ❌ Invalid credentials
        if user is None:
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # ❌ Email not verified
        if not user.email_verified:
            return Response(
                {"error": "Email not verified."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "email": user.email,
                "role": user.role
            },
            status=status.HTTP_200_OK
        )

# -------------------------------------------------------
# OTP VERIFICATION VIEWS
# -------------------------------------------------------

class OTPRequestView(APIView):
    """
    Endpoint to request OTP for email verification.
    
    This endpoint generates an OTP, stores it in the database, and queues
    an email through Celery workers for asynchronous sending.
    
    Accepts:
    - email: The user's email address
    
    Returns:
    - Success message with email address if OTP was queued successfully
    - Error message if user not found or any other error occurs
    
    Architecture:
    - OTP generation: synchronous (happens immediately)
    - OTP storage: synchronous (happens immediately)
    - Email sending: asynchronous (queued to Celery workers)
    - API Response: returns immediately without waiting for email send
    
    Example cURL:
        curl -X POST http://localhost:8000/api/accounts/otp/request/ \
          -H "Content-Type: application/json" \
          -d '{"email": "user@example.com"}'
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_request'

    @swagger_auto_schema(
        request_body=OTPRequestSerializer,
        responses={200: "OTP sent", 400: "Bad Request"},
        tags=["Accounts"],
        operation_description="Send OTP for email_verification, password_reset, or login_otp."
    )

    def post(self, request):
        from utils.email_service import EmailService

        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = serializer.validated_data['purpose']
        user = User.objects.filter(email=email).first()
        if user:
            EmailService.send_verification_otp(
                user,
                purpose=purpose,
            )

        return Response(
            {
                "message": "If an account exists for this email, an OTP has been sent."
            },
            status=status.HTTP_200_OK
        )


class OTPVerificationView(APIView):
    """
    Endpoint to verify OTP code.
    
    Accepts:
    - email: The user's email address
    - otp: The OTP code (4-6 digits)
    
    Returns:
    - Success message if OTP is valid
    - Error message if OTP is invalid, expired, or doesn't match
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_verify'

    @swagger_auto_schema(
        request_body=OTPVerificationSerializer,
        responses={200: "OTP verified", 400: "Invalid OTP"},
        tags=["Accounts"],
        operation_description="Verify OTP for email_verification, password_reset, or login_otp."
    )

    def post(self, request):
        from utils.email_service import EmailService

        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data['purpose']

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify OTP against the correct purpose
        result = EmailService.verify_otp(user, otp_code, purpose=purpose)

        if not result['success']:
            return Response(
                {"error": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # For email_verification, only confirm verification.
        if purpose == 'email_verification':
            return Response(
                {
                    "message": "Email verified successfully.",
                    "email": user.email,
                    "role": user.role
                },
                status=status.HTTP_200_OK
            )

        if purpose == 'login_otp':
            return Response(
                {"message": "OTP verified successfully for login."},
                status=status.HTTP_200_OK
            )

        return Response(
            {"message": "OTP verified. You may now reset your password."},
            status=status.HTTP_200_OK
        )


class PasswordResetView(APIView):
    """
    Final step of the forgot-password flow.

    Accepts:
    - email
    - new_password

    Checks that a verified password_reset OTP exists for this user,
    sets the new password, then deletes the OTP record.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    @swagger_auto_schema(
        request_body=PasswordResetSerializer,
        responses={200: "Password reset successful", 400: "OTP not verified"},
        tags=["Accounts"],
        operation_description="Reset password after verified password_reset OTP."
    )

    def post(self, request):
        from accounts.models import EmailOTP

        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"error": "Password reset request is invalid."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Gate: a verified password_reset OTP must exist
        try:
            otp_instance = EmailOTP.objects.select_for_update().get(
                user=user,
                purpose='password_reset',
                is_verified=True,
            )
        except EmailOTP.DoesNotExist:
            return Response(
                {"error": "Password reset request is invalid."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set new password
        user.set_password(new_password)
        user.save(update_fields=['password'])

        # Delete the OTP record so it cannot be reused
        otp_instance.delete()

        return Response(
            {"message": "Password reset successfully. You can now log in."},
            status=status.HTTP_200_OK
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ChangePasswordSerializer,
        responses={200: "Password changed successfully", 400: "Validation error", 403: "Forbidden"},
        tags=["Accounts"],
        operation_description="Change password for authenticated student users and force re-login.",
    )
    def post(self, request):
        if request.user.role != 'student':
            return Response(
                {'error': 'Only student users can change password from account settings.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save(update_fields=['password'])

        invalidate_user_session(request.user.pk)
        clear_user_me_cache(request.user.pk)

        return Response(
            {'message': 'Password changed successfully. Please log in again.'},
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------
# RBAC ADMIN PORTAL VIEWS (ADDITIVE)
# -------------------------------------------------------

ADMIN_PORTAL_ROLES = ('superadmin', 'subadmin', 'sales')


class RBACAdminLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RBACLoginSerializer,
        responses={200: 'OTP sent', 401: 'Invalid credentials', 403: 'Not authorized'},
        tags=['Admin RBAC'],
        operation_description='Admin portal login with email/password. Sends login_otp on success.',
    )
    def post(self, request):
        from utils.email_service import EmailService

        serializer = RBACLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(request, email=email, password=password)
        if not user:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        if user.role not in ADMIN_PORTAL_ROLES:
            return Response({'error': 'Not authorized for admin portal.'}, status=status.HTTP_403_FORBIDDEN)

        if not user.is_active:
            return Response({'error': 'Account is deactivated.'}, status=status.HTTP_403_FORBIDDEN)

        EmailService.send_verification_otp(user, purpose='login_otp', otp_length=6)
        return Response({'message': 'OTP sent to your email.'}, status=status.HTTP_200_OK)


class RBACAdminOTPVerifyView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=RBACOTPVerifySerializer,
        responses={200: 'Login successful', 400: 'Invalid OTP'},
        tags=['Admin RBAC'],
        operation_description='Verify login OTP and issue JWT tokens for admin portal users.',
    )
    def post(self, request):
        from utils.email_service import EmailService

        serializer = RBACOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        user = User.objects.filter(email=email).first()
        if not user or user.role not in ADMIN_PORTAL_ROLES:
            return Response({'error': 'Invalid credentials or verification code.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_active:
            return Response({'error': 'Account is deactivated.'}, status=status.HTTP_403_FORBIDDEN)

        result = EmailService.verify_otp(user, otp, purpose='login_otp')
        if not result['success']:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        clear_user_invalidation(user.pk)

        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=['email_verified'])

        tokens = get_tokens_for_user(user)
        return Response(
            {
                'message': 'Login successful.',
                'refresh': tokens['refresh'],
                'access': tokens['access'],
                'role': user.role,
            },
            status=status.HTTP_200_OK,
        )


class RBACMeView(APIView):
    permission_classes = [IsAdminPortalUser]

    @swagger_auto_schema(security=[{"Bearer": []}],tags=['Admin RBAC'], operation_description='Get current admin portal user profile and module access.')
    def get(self, request):
        cached_payload = get_cached_me(request.user.pk, request.user.role)
        if cached_payload is not None and cached_payload.get('role') == request.user.role:
            return Response(cached_payload, status=status.HTTP_200_OK)

        serializer = MeSerializer(request.user)
        payload = serializer.data
        set_cached_me(request.user.pk, request.user.role, payload)
        return Response(payload, status=status.HTTP_200_OK)


class ModuleListView(APIView):
    permission_classes = [CanManageSubadmins]
    pagination_class = AccountsListPagination

    @swagger_auto_schema(tags=['Admin RBAC'], operation_description='List active modules for subadmin assignment.')
    def get(self, request):
        modules = Module.objects.filter(is_active=True)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(modules, request, view=self)
        return paginator.get_paginated_response(ModuleSerializer(page, many=True).data)


class CreateSubAdminView(APIView):
    permission_classes = [CanManageSubadmins]

    @swagger_auto_schema(
        request_body=CreateSubAdminSerializer,
        tags=['Admin RBAC'],
        operation_description='Create a subadmin and assign module access.',
    )
    @transaction.atomic
    def post(self, request):
        serializer = CreateSubAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            user = User.objects.create_user(
                email=data['email'],
                password=data['password'],
                role='subadmin',
                name=data['name'],
            )

            profile = SubAdminProfile.objects.create(user=user, created_by=request.user)
            modules = Module.objects.filter(name__in=data['modules'])
            profile.allowed_modules.set(modules)
        except IntegrityError:
            transaction.set_rollback(True)
            return Response(
                {'error': 'SubAdmin could not be created. Please retry.'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                'message': 'SubAdmin created successfully.',
                'user_id': user.id,
                'assigned_modules': profile.get_module_names(),
            },
            status=status.HTTP_201_CREATED,
        )


class ListSubAdminsView(APIView):
    permission_classes = [CanManageSubadmins]
    pagination_class = AccountsListPagination

    @swagger_auto_schema(tags=['Admin RBAC'], operation_description='List all subadmins and assigned modules.')
    def get(self, request):
        users = (
            _manageable_subadmin_users(request.user)
            .select_related('subadmin_profile__created_by')
            .prefetch_related('subadmin_profile__allowed_modules')
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(SubAdminListSerializer(page, many=True).data)


class UpdateSubAdminAccessView(APIView):
    permission_classes = [CanManageSubadmins]

    @swagger_auto_schema(
        request_body=UpdateSubAdminModulesSerializer,
        tags=['Admin RBAC'],
        operation_description='Update allowed modules for a subadmin.',
    )
    @transaction.atomic
    def patch(self, request, user_id):
        serializer = UpdateSubAdminModulesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = _manageable_subadmin_profiles(request.user).select_for_update().get(user_id=user_id)
        except SubAdminProfile.DoesNotExist:
            return Response({'error': 'SubAdmin not found.'}, status=status.HTTP_404_NOT_FOUND)

        modules = Module.objects.filter(name__in=serializer.validated_data['modules'])
        profile.allowed_modules.set(modules)
        transaction.on_commit(lambda: invalidate_user_session(profile.user_id))
        transaction.on_commit(lambda: clear_user_me_cache(profile.user_id))

        return Response(
            {
                'message': 'Modules updated.',
                'updated_modules': profile.get_module_names(),
            },
            status=status.HTTP_200_OK,
        )


class UpdateSubAdminRoleView(APIView):
    permission_classes = [CanManageSubadmins]

    @swagger_auto_schema(
        request_body=UpdateSubAdminRoleSerializer,
        tags=['Admin RBAC'],
        operation_description='Update role for a subadmin user. Allowed roles: subadmin, sales, student.',
    )
    @transaction.atomic
    def patch(self, request, user_id):
        serializer = UpdateSubAdminRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = _manageable_subadmin_users(request.user).select_for_update().get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'SubAdmin not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.pk == user.pk and serializer.validated_data['role'] != 'superadmin':
            return Response(
                {'error': 'You cannot change your own role from this endpoint.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.role = serializer.validated_data['role']
        user.save(update_fields=['role'])

        transaction.on_commit(lambda: invalidate_user_session(user.pk))
        transaction.on_commit(lambda: clear_user_me_cache(user.pk))

        return Response(
            {
                'message': 'Role updated.',
                'role': user.role,
            },
            status=status.HTTP_200_OK,
        )


class ToggleSubAdminStatusView(APIView):
    permission_classes = [CanManageSubadmins]

    @swagger_auto_schema(tags=['Admin RBAC'], operation_description='Activate or deactivate a subadmin account.')
    @transaction.atomic
    def patch(self, request, user_id):
        try:
            user = _manageable_subadmin_users(request.user).select_for_update().get(id=user_id, role='subadmin')
        except User.DoesNotExist:
            return Response({'error': 'SubAdmin not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.pk == user.pk and user.is_active:
            return Response(
                {'error': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])

        try:
            user.subadmin_profile.is_active = user.is_active
            user.subadmin_profile.save(update_fields=['is_active'])
        except SubAdminProfile.DoesNotExist:
            pass

        if not user.is_active:
            transaction.on_commit(lambda: invalidate_user_session(user.pk))
            transaction.on_commit(lambda: clear_user_me_cache(user.pk))

        return Response(
            {
                'message': f"SubAdmin {'activated' if user.is_active else 'deactivated'}.",
                'is_active': user.is_active,
            },
            status=status.HTTP_200_OK,
        )


class DeleteSubAdminView(APIView):
    permission_classes = [CanManageSubadmins]

    @swagger_auto_schema(tags=['Admin RBAC'], operation_description='Delete a subadmin account.')
    @transaction.atomic
    def delete(self, request, user_id):
        try:
            user = _manageable_subadmin_users(request.user).select_for_update().get(id=user_id, role='subadmin')
        except User.DoesNotExist:
            return Response({'error': 'SubAdmin not found.'}, status=status.HTTP_404_NOT_FOUND)

        user_pk = user.pk
        user.delete()
        transaction.on_commit(lambda: invalidate_user_session(user_pk))
        transaction.on_commit(lambda: clear_user_me_cache(user_pk))
        return Response({'message': 'SubAdmin deleted.'}, status=status.HTTP_200_OK)
