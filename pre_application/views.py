from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.db.models import Q
from django.db import transaction
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access_control import filter_preapplications_for_user
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
    queryset = manager.with_referral().order_by("-created_at")
    if getattr(request.user, "is_authenticated", False):
        return filter_preapplications_for_user(request.user, queryset)
    return queryset


WIDGET_FILTERS = {
    "total_received": None,
    "today": "today",
    "enquiry_done": PreApplication.STATUS_COMPLETED,
    "pending_enquiry": PreApplication.STATUS_PENDING,
    "not_interested": PreApplication.STATUS_NOT_INTERESTED,
}


STATUS_FILTERS = {
    "pending": PreApplication.STATUS_PENDING,
    "completed": PreApplication.STATUS_COMPLETED,
    "enquiry_done": PreApplication.STATUS_COMPLETED,
    "not_interested": PreApplication.STATUS_NOT_INTERESTED,
    "not interested": PreApplication.STATUS_NOT_INTERESTED,
}


def _apply_preapplication_list_filters(request, queryset):
    widget = (request.query_params.get("widget") or "").strip().lower()
    if widget:
        if widget not in WIDGET_FILTERS:
            allowed_widgets = ", ".join(sorted(WIDGET_FILTERS.keys()))
            raise ValueError(f"Invalid widget. Allowed values: {allowed_widgets}.")
        widget_value = WIDGET_FILTERS[widget]
        if widget_value == "today":
            queryset = queryset.filter(created_at__date=timezone.localdate())
        elif widget_value:
            queryset = queryset.filter(status=widget_value)

    status_filter = (request.query_params.get("status") or "").strip().lower()
    if status_filter:
        normalized_status = STATUS_FILTERS.get(status_filter)
        if not normalized_status:
            allowed_statuses = ", ".join(sorted(STATUS_FILTERS.keys()))
            raise ValueError(f"Invalid status. Allowed values: {allowed_statuses}.")
        queryset = queryset.filter(status=normalized_status)

    search = (request.query_params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(enquiry_token__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(whatsapp_no__icontains=search)
            | Q(alternate_phone__icontains=search)
        )

    birthplace_state = (request.query_params.get("birthplace_state") or "").strip()
    if birthplace_state:
        queryset = queryset.filter(birthplace_state__iexact=birthplace_state)

    college_state = (request.query_params.get("college_state") or "").strip()
    if college_state:
        queryset = queryset.filter(college_state__iexact=college_state)

    passing_year = (request.query_params.get("passing_year") or "").strip()
    if passing_year:
        queryset = queryset.filter(passing_year=passing_year)

    date_from_raw = (request.query_params.get("date_from") or "").strip()
    date_to_raw = (request.query_params.get("date_to") or "").strip()

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    if date_from_raw and not date_from:
        raise ValueError("Invalid date_from. Use YYYY-MM-DD format.")
    if date_to_raw and not date_to:
        raise ValueError("Invalid date_to. Use YYYY-MM-DD format.")

    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from cannot be after date_to.")

    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    return queryset


def _scoped_preapplication_queryset_for_write(request, include_deleted=False):
    manager = PreApplication.all_objects if include_deleted else PreApplication.objects
    queryset = manager.all()
    return filter_preapplications_for_user(request.user, queryset)


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
    required_module_action = 'view'
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
            openapi.Parameter(
                "widget",
                openapi.IN_QUERY,
                description="Widget preset: total_received, today, enquiry_done, pending_enquiry, not_interested.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Optional status filter: pending, completed/enquiry_done, not_interested.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                description="Search by enquiry token, name, email, or phone.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "birthplace_state",
                openapi.IN_QUERY,
                description="Filter by birthplace state.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "college_state",
                openapi.IN_QUERY,
                description="Filter by college state.",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "passing_year",
                openapi.IN_QUERY,
                description="Filter by passing year (YYYY).",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "date_from",
                openapi.IN_QUERY,
                description="Filter created_at from date (YYYY-MM-DD).",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "date_to",
                openapi.IN_QUERY,
                description="Filter created_at up to date (YYYY-MM-DD).",
                type=openapi.TYPE_STRING,
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
            400: "Invalid query parameter value.",
            401: "Authentication credentials were not provided.",
            403: "You do not have permission to perform this action.",
        },
        operation_description=(
            "List pre-applications for the custom admin panel with widget presets and drill-down filters. "
            "Use widget for top-card pages and combine with status/date/state/year/search for deeper filtering."
        ),
    )
    def get(self, request):
        queryset = _filtered_preapplication_queryset(request)
        try:
            queryset = _apply_preapplication_list_filters(request, queryset)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
            _scoped_preapplication_queryset_for_write(request),
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
        pre_application = get_object_or_404(
            _scoped_preapplication_queryset_for_write(request),
            enquiry_token=token,
        )
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
        pre_application = get_object_or_404(
            _scoped_preapplication_queryset_for_write(request),
            pk=pk,
        )
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
            _scoped_preapplication_queryset_for_write(request, include_deleted=True).select_for_update(),
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
            _scoped_preapplication_queryset_for_write(request, include_deleted=True).select_for_update(),
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
            _scoped_preapplication_queryset_for_write(request, include_deleted=True).select_for_update(),
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
            _scoped_preapplication_queryset_for_write(request, include_deleted=True).select_for_update(),
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
