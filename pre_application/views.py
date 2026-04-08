from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasModuleAccess, IsAdminPortalUser

from .models import PreApplication, ReferalCode
from .pagination import PreApplicationPagination
from .serializers import (
    PreApplicationActionResponseSerializer,
    PreApplicationAdminListSerializer,
    PreApplicationArchiveRequestSerializer,
    PreApplicationLookupSerializer,
    PreApplicationSerializer,
    PreApplicationStatusUpdateSerializer,
    ReferalCodeSerializer,
    ReferralValidationResponseSerializer,
)
from .services import ReferralGenerationError, create_referral_for_pre_application


SUBMIT_RESPONSE_EXAMPLE = {
    "enquiry_token": "ENQ000123",
    "first_name": "Asha",
    "last_name": "Patel",
    "email": "asha@example.com",
    "whatsapp_no": "+919876543210",
    "alternate_phone": None,
    "birthplace_state": "Gujarat",
    "qualification": "B.Tech",
    "specialization": "CSE",
    "college_name": "Example College",
    "college_state": "Gujarat",
    "passing_year": "2024",
    "preferred_time": "Evening",
    "status": "pending",
    "verified": False,
    "is_deleted": False,
    "deleted_at": None,
    "deleted_reason": None,
    "deleted_by": None,
    "created_at": "2026-03-27T09:00:00Z",
}

LOOKUP_RESPONSE_EXAMPLE = {
    "id": 12,
    "enquiry_token": "ENQ000123",
    "full_name": "Asha Patel",
    "first_name": "Asha",
    "last_name": "Patel",
    "email": "asha@example.com",
    "whatsapp_no": "+919876543210",
    "alternate_phone": None,
    "verified": True,
    "reference_code": "AB12CD34",
}

STATUS_UPDATE_RESPONSE_EXAMPLE = {
    **SUBMIT_RESPONSE_EXAMPLE,
    "status": "completed",
}

REFERRAL_CREATE_RESPONSE_EXAMPLE = {
    "id": 5,
    "student": 12,
    "code": "AB12CD34",
    "status": "not_used",
    "is_used": False,
    "created_at": "2026-03-27T09:10:00Z",
    "message": "Referral code created and approval email sent",
}

ARCHIVE_RESPONSE_EXAMPLE = {
    "message": "Pre-application archived successfully.",
    "enquiry_token": "ENQ000123",
    "is_deleted": True,
}

RESTORE_RESPONSE_EXAMPLE = {
    "message": "Pre-application restored successfully.",
    "enquiry_token": "ENQ000123",
    "is_deleted": False,
}


def _is_superadmin_user(user):
    return getattr(user, "is_superuser", False) or getattr(user, "role", None) == "superadmin"


def _include_deleted_requested(request):
    return (request.query_params.get("include_deleted") or "").strip().lower() == "true"


def _filtered_preapplication_queryset(request):
    manager = PreApplication.objects
    if _include_deleted_requested(request) and _is_superadmin_user(request.user):
        manager = PreApplication.all_objects
    return manager.with_referral().order_by("-created_at")


def _soft_delete_pre_application(pre_application, user, reason=None):
    if not pre_application.is_deleted:
        pre_application.is_deleted = True
        pre_application.deleted_at = timezone.now()
        pre_application.deleted_by = user

    pre_application.deleted_reason = reason or None
    pre_application.save(
        update_fields=["is_deleted", "deleted_at", "deleted_by", "deleted_reason"]
    )


def _restore_pre_application(pre_application):
    pre_application.is_deleted = False
    pre_application.deleted_at = None
    pre_application.deleted_by = None
    pre_application.deleted_reason = None
    pre_application.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "deleted_reason"])


class PreApplicationCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=PreApplicationSerializer,
        security=[],
        responses={
            201: openapi.Response(
                description="Pre-application created successfully.",
                schema=PreApplicationSerializer,
                examples={"application/json": SUBMIT_RESPONSE_EXAMPLE},
            ),
            400: "Validation Error",
        },
        tags=["Pre Application"],
        operation_description=(
            "Submit the pre-application form. "
            "The backend generates a unique enquiry token and returns it in the success payload."
        ),
    )
    def post(self, request):
        serializer = PreApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PreApplicationListAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'
    pagination_class = PreApplicationPagination

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "page",
                openapi.IN_QUERY,
                description="Page number",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "page_size",
                openapi.IN_QUERY,
                description="Items per page",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
            openapi.Parameter(
                "include_deleted",
                openapi.IN_QUERY,
                description="Set true to include archived rows (superadmin only).",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of pre-applications for admin panel.",
                examples={
                    "application/json": {
                        "count": 2,
                        "next": None,
                        "previous": None,
                        "results": [
                            SUBMIT_RESPONSE_EXAMPLE,
                        ],
                    }
                },
            ),
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
        },
        operation_description=(
            "List pre-applications for the custom admin panel. "
            "Each row includes the enquiry token and referral-linked summary fields."
        ),
    )
    def get(self, request):
        queryset = _filtered_preapplication_queryset(request)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = PreApplicationAdminListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PreApplicationByEnquiryTokenAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "enquiry_token",
                openapi.IN_PATH,
                description="Enquiry token in ENQ123456 format",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "include_deleted",
                openapi.IN_QUERY,
                description="Set true to include archived rows (superadmin only).",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Candidate details found for enquiry token.",
                schema=PreApplicationLookupSerializer,
                examples={"application/json": SUBMIT_RESPONSE_EXAMPLE},
            ),
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
        operation_description="Fetch candidate details by enquiry token for admin referral workflows.",
    )
    def get(self, request, enquiry_token):
        token = enquiry_token.strip().upper()
        pre_application = get_object_or_404(
            _filtered_preapplication_queryset(request),
            enquiry_token=token,
        )
        serializer = PreApplicationLookupSerializer(pre_application)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        request_body=PreApplicationStatusUpdateSerializer,
        manual_parameters=[
            openapi.Parameter(
                "enquiry_token",
                openapi.IN_PATH,
                description="Enquiry token in ENQ123456 format",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: openapi.Response(
                description="Pre-application status updated successfully.",
                schema=PreApplicationSerializer,
                examples={"application/json": STATUS_UPDATE_RESPONSE_EXAMPLE},
            ),
            400: "Validation error",
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
        operation_description=(
            "Update only the pre-application status by enquiry token. "
            "Allowed roles: admin, superadmin, and Django superuser."
        ),
    )
    def patch(self, request, enquiry_token):
        token = enquiry_token.strip().upper()
        pre_application = get_object_or_404(
            PreApplication.objects.select_related("referal_codes"),
            enquiry_token=token,
        )
        if pre_application.is_deleted:
            return Response(
                {"error": "Cannot update status for archived pre-application."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PreApplicationStatusUpdateSerializer(
            pre_application,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = PreApplicationSerializer(pre_application)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class PreApplicationLookupAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "email",
                openapi.IN_QUERY,
                description="Unique candidate email address",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "enquiry_token",
                openapi.IN_QUERY,
                description="Unique enquiry token in ENQ123456 format",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "include_deleted",
                openapi.IN_QUERY,
                description="Set true to include archived rows (superadmin only).",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Candidate details found.",
                schema=PreApplicationLookupSerializer,
                examples={"application/json": SUBMIT_RESPONSE_EXAMPLE},
            ),
            400: "Provide exactly one of email or enquiry_token.",
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
        operation_description=(
            "Fetch a specific pre-application by unique email or enquiry token for the admin panel."
        ),
    )
    def get(self, request):
        email = (request.query_params.get("email") or "").strip()
        enquiry_token = (request.query_params.get("enquiry_token") or "").strip().upper()

        if bool(email) == bool(enquiry_token):
            return Response(
                {"error": "Provide exactly one of email or enquiry_token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = _filtered_preapplication_queryset(request)
        if email:
            pre_application = get_object_or_404(queryset, email=email)
        else:
            pre_application = get_object_or_404(queryset, enquiry_token=enquiry_token)

        serializer = PreApplicationLookupSerializer(pre_application)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BaseCreateReferralAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'reference_code'

    def create_referral_response(self, pre_application):
        try:
            referral = create_referral_for_pre_application(pre_application)
        except ReferralGenerationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReferalCodeSerializer(referral)
        return Response(
            {
                **serializer.data,
                "message": "Referral code created and approval email sent",
            },
            status=status.HTTP_201_CREATED,
        )


class CreateReferralByEnquiryTokenAPIView(BaseCreateReferralAPIView):
    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "enquiry_token",
                openapi.IN_PATH,
                description="Enquiry token in ENQ123456 format",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            201: openapi.Response(
                description="Referral code created successfully.",
                schema=ReferalCodeSerializer,
                examples={"application/json": REFERRAL_CREATE_RESPONSE_EXAMPLE},
            ),
            400: "Referral already exists for this student",
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
        operation_description=(
            "Generate a referral code for a pre-application identified by enquiry token. "
            "This is the canonical admin route."
        ),
    )
    def post(self, request, enquiry_token):
        token = enquiry_token.strip().upper()
        pre_application = get_object_or_404(PreApplication.objects, enquiry_token=token)
        return self.create_referral_response(pre_application)


class CreateReferralAPIView(BaseCreateReferralAPIView):
    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "pk",
                openapi.IN_PATH,
                description="Pre-application primary key",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={
            201: openapi.Response(
                description="Referral code created successfully.",
                schema=ReferalCodeSerializer,
                examples={"application/json": REFERRAL_CREATE_RESPONSE_EXAMPLE},
            ),
            400: "Referral already exists for this student",
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
        operation_description=(
            "Generate a referral code for a pre-application identified by primary key. "
            "This legacy admin route is retained for backward compatibility."
        ),
    )
    def post(self, request, pk):
        pre_application = get_object_or_404(PreApplication.objects, pk=pk)
        return self.create_referral_response(pre_application)


class ArchivePreApplicationByEnquiryTokenAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        request_body=PreApplicationArchiveRequestSerializer,
        responses={
            200: openapi.Response(
                description="Pre-application archived successfully.",
                schema=PreApplicationActionResponseSerializer,
                examples={"application/json": ARCHIVE_RESPONSE_EXAMPLE},
            ),
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
    )
    @transaction.atomic
    def patch(self, request, enquiry_token):
        token = enquiry_token.strip().upper()
        pre_application = get_object_or_404(
            PreApplication.all_objects.select_for_update(),
            enquiry_token=token,
        )
        serializer = PreApplicationArchiveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _soft_delete_pre_application(
            pre_application,
            request.user,
            serializer.validated_data.get("deleted_reason"),
        )

        return Response(
            {
                "message": "Pre-application archived successfully.",
                "enquiry_token": pre_application.enquiry_token,
                "is_deleted": pre_application.is_deleted,
            },
            status=status.HTTP_200_OK,
        )


class ArchivePreApplicationAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        request_body=PreApplicationArchiveRequestSerializer,
        responses={
            200: openapi.Response(
                description="Pre-application archived successfully.",
                schema=PreApplicationActionResponseSerializer,
                examples={"application/json": ARCHIVE_RESPONSE_EXAMPLE},
            ),
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
    )
    @transaction.atomic
    def patch(self, request, pk):
        pre_application = get_object_or_404(
            PreApplication.all_objects.select_for_update(),
            pk=pk,
        )
        serializer = PreApplicationArchiveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _soft_delete_pre_application(
            pre_application,
            request.user,
            serializer.validated_data.get("deleted_reason"),
        )

        return Response(
            {
                "message": "Pre-application archived successfully.",
                "enquiry_token": pre_application.enquiry_token,
                "is_deleted": pre_application.is_deleted,
            },
            status=status.HTTP_200_OK,
        )


class RestorePreApplicationByEnquiryTokenAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        responses={
            200: openapi.Response(
                description="Pre-application restored successfully.",
                schema=PreApplicationActionResponseSerializer,
                examples={"application/json": RESTORE_RESPONSE_EXAMPLE},
            ),
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
    )
    @transaction.atomic
    def patch(self, request, enquiry_token):
        token = enquiry_token.strip().upper()
        pre_application = get_object_or_404(
            PreApplication.all_objects.select_for_update(),
            enquiry_token=token,
        )
        _restore_pre_application(pre_application)

        return Response(
            {
                "message": "Pre-application restored successfully.",
                "enquiry_token": pre_application.enquiry_token,
                "is_deleted": pre_application.is_deleted,
            },
            status=status.HTTP_200_OK,
        )


class RestorePreApplicationAPIView(APIView):
    permission_classes = [IsAdminPortalUser, HasModuleAccess]
    required_module = 'enquiry_form'

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Pre Application"],
        responses={
            200: openapi.Response(
                description="Pre-application restored successfully.",
                schema=PreApplicationActionResponseSerializer,
                examples={"application/json": RESTORE_RESPONSE_EXAMPLE},
            ),
            403: "You do not have permission to perform this action.",
            404: "Pre-application not found",
        },
    )
    @transaction.atomic
    def patch(self, request, pk):
        pre_application = get_object_or_404(
            PreApplication.all_objects.select_for_update(),
            pk=pk,
        )
        _restore_pre_application(pre_application)

        return Response(
            {
                "message": "Pre-application restored successfully.",
                "enquiry_token": pre_application.enquiry_token,
                "is_deleted": pre_application.is_deleted,
            },
            status=status.HTTP_200_OK,
        )


class CheckReferralCodeAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        security=[],
        tags=["Pre Application"],
        manual_parameters=[
            openapi.Parameter(
                "code",
                openapi.IN_PATH,
                description="Referral code to validate",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: openapi.Response(
                description="Referral code is valid.",
                schema=ReferralValidationResponseSerializer,
                examples={"application/json": LOOKUP_RESPONSE_EXAMPLE},
            ),
            404: "Referral code not found",
        },
        operation_description=(
            "Validate a referral code and return the linked candidate details "
            "from the same pre-application record."
        ),
    )
    def get(self, request, code):
        referral = get_object_or_404(
            ReferalCode.objects.select_related("student").filter(
                student_id__in=PreApplication.objects.values("pk")
            ),
            code=code,
        )
        serializer = ReferralValidationResponseSerializer(referral.student)
        return Response(serializer.data, status=status.HTTP_200_OK)
