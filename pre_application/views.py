from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from admin_panel.permissions import IsSuperuserOrAdminOrSubadmin

from .models import PreApplication, ReferalCode
from .pagination import PreApplicationPagination
from .serializers import (
    PreApplicationLookupSerializer,
    PreApplicationSerializer,
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
    "verified": False,
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

REFERRAL_CREATE_RESPONSE_EXAMPLE = {
    "id": 5,
    "student": 12,
    "code": "AB12CD34",
    "is_used": False,
    "created_at": "2026-03-27T09:10:00Z",
    "message": "Referral code created and approval email sent",
}


class PreApplicationCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=PreApplicationSerializer,
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
    permission_classes = [IsSuperuserOrAdminOrSubadmin]
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
                            LOOKUP_RESPONSE_EXAMPLE,
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
        queryset = PreApplication.objects.select_related("referal_codes").order_by("-created_at")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = PreApplicationLookupSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PreApplicationByEnquiryTokenAPIView(APIView):
    permission_classes = [IsSuperuserOrAdminOrSubadmin]

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
            200: openapi.Response(
                description="Candidate details found for enquiry token.",
                schema=PreApplicationLookupSerializer,
                examples={"application/json": LOOKUP_RESPONSE_EXAMPLE},
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
            PreApplication.objects.select_related("referal_codes"),
            enquiry_token=token,
        )
        serializer = PreApplicationLookupSerializer(pre_application)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PreApplicationLookupAPIView(APIView):
    permission_classes = [IsSuperuserOrAdminOrSubadmin]

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
        ],
        responses={
            200: openapi.Response(
                description="Candidate details found.",
                schema=PreApplicationLookupSerializer,
                examples={"application/json": LOOKUP_RESPONSE_EXAMPLE},
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

        queryset = PreApplication.objects.select_related("referal_codes")
        if email:
            pre_application = get_object_or_404(queryset, email=email)
        else:
            pre_application = get_object_or_404(queryset, enquiry_token=enquiry_token)

        serializer = PreApplicationLookupSerializer(pre_application)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BaseCreateReferralAPIView(APIView):
    permission_classes = [IsSuperuserOrAdminOrSubadmin]

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
        pre_application = get_object_or_404(PreApplication, enquiry_token=token)
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
        pre_application = get_object_or_404(PreApplication, pk=pk)
        return self.create_referral_response(pre_application)


class CheckReferralCodeAPIView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
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
            ReferalCode.objects.select_related("student"),
            code=code,
        )
        serializer = ReferralValidationResponseSerializer(referral.student)
        return Response(serializer.data, status=status.HTTP_200_OK)
