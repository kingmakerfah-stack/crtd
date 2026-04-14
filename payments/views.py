import json
import logging

import razorpay
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from subscription.models import SubscriptionPlan

from .models import PaymentHistory, StudentPayment
from .pagination import PaymentPagination
from .serializers import PaymentHistorySerializer
from .services import create_razorpay_order, get_razorpay_client
from .student_subscription_service import (
    activate_subscription_from_student_payment,
    build_subscription_summary,
    has_active_subscription,
    mark_student_payment_failed,
    mark_student_payment_success,
)

logger = logging.getLogger(__name__)


PAYMENT_INITIATE_RESPONSE_EXAMPLE = {
    "order_id": "order_RZP_123456789",
    "amount": 200000,
    "key": "rzp_live_public_key",
}

PAYMENT_VERIFY_REQUEST_EXAMPLE = {
    "razorpay_payment_id": "pay_123456789",
    "razorpay_order_id": "order_RZP_123456789",
    "razorpay_signature": "generated_signature",
}

PAYMENT_FAILED_REQUEST_EXAMPLE = {
    "razorpay_order_id": "order_RZP_123456789",
    "razorpay_payment_id": "pay_123456789",
}


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    security=[{"Bearer": []}],
    operation_description="Create a Razorpay order for student subscription payment.",
    responses={
        201: openapi.Response(
            description="Order created successfully.",
            examples={"application/json": PAYMENT_INITIATE_RESPONSE_EXAMPLE},
        ),
        400: "Profile incomplete or active subscription exists.",
        401: "Authentication credentials were not provided.",
        403: "Student role required.",
        404: "Subscription plan not found.",
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStudent])
def create_order(request):
    student_profile = getattr(request.user, "student_profile", None)
    if not student_profile:
        return Response({"error": "Student profile not found."}, status=status.HTTP_400_BAD_REQUEST)

    if not student_profile.profile_completed:
        return Response(
            {"error": "Complete profile first"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if has_active_subscription(request.user):
        return Response(
            {"error": "Active subscription already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    amount = int(getattr(settings, "SUBSCRIPTION_AMOUNT_PAISE", 0) or 0)
    if amount <= 0:
        plan = SubscriptionPlan.objects.filter(is_active=True).first()
        if not plan:
            return Response(
                {"error": "Subscription plan not found. Contact admin."},
                status=status.HTTP_404_NOT_FOUND,
            )
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


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["razorpay_payment_id", "razorpay_order_id", "razorpay_signature"],
        properties={
            "razorpay_payment_id": openapi.Schema(type=openapi.TYPE_STRING),
            "razorpay_order_id": openapi.Schema(type=openapi.TYPE_STRING),
            "razorpay_signature": openapi.Schema(type=openapi.TYPE_STRING),
        },
        example=PAYMENT_VERIFY_REQUEST_EXAMPLE,
    ),
    operation_description="Verify Razorpay signature from frontend. Does not activate subscription.",
    responses={
        200: "Payment verified. Awaiting webhook confirmation.",
        400: "Missing params or signature verification failed.",
        401: "Authentication credentials were not provided.",
        403: "Student role required.",
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStudent])
def verify_payment(request):
    client = get_razorpay_client()

    payment_id = request.data.get("razorpay_payment_id")
    order_id = request.data.get("razorpay_order_id")
    signature = request.data.get("razorpay_signature")

    if not payment_id or not order_id or not signature:
        return Response({"error": "Missing payment parameters"}, status=status.HTTP_400_BAD_REQUEST)

    params = {
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_id,
        "razorpay_signature": signature,
    }

    try:
        client.utility.verify_payment_signature(params)
    except razorpay.errors.SignatureVerificationError:
        return Response({"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("Payment verification error")
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {"message": "Payment verified. Awaiting webhook confirmation."},
        status=status.HTTP_200_OK,
    )


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    manual_parameters=[
        openapi.Parameter(
            "X-Razorpay-Signature",
            openapi.IN_HEADER,
            description="Razorpay webhook signature",
            type=openapi.TYPE_STRING,
            required=True,
        )
    ],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        description="Raw Razorpay webhook payload",
    ),
    operation_description="Mandatory Razorpay webhook endpoint. Subscription activation is processed only here.",
    responses={200: "Webhook received and processed (or safely ignored)."},
)
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_exempt
def razorpay_webhook(request):
    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    client = get_razorpay_client()
    try:
        client.utility.verify_webhook_signature(
            payload,
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET,
        )
    except Exception:
        logger.warning("Invalid Razorpay webhook signature")
        return HttpResponse(status=200)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Invalid webhook payload JSON")
        return HttpResponse(status=200)

    event = data.get("event")
    entity = (data.get("payload") or {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")

    if not order_id:
        logger.warning("Webhook payload missing order_id")
        return HttpResponse(status=200)

    try:
        if event == "payment.captured":
            payment, changed = mark_student_payment_success(
                order_id=order_id,
                payment_id=payment_id,
            )
            if changed:
                activate_subscription_from_student_payment(payment)
            logger.info("Processed payment.captured", extra={"order_id": order_id, "changed": changed})
            return HttpResponse(status=200)

        if event == "payment.failed":
            mark_student_payment_failed(order_id=order_id, payment_id=payment_id)
            logger.info("Processed payment.failed", extra={"order_id": order_id})
            return HttpResponse(status=200)

        logger.info("Ignored webhook event", extra={"event": event, "order_id": order_id})
        return HttpResponse(status=200)
    except StudentPayment.DoesNotExist:
        logger.warning("StudentPayment not found for webhook", extra={"order_id": order_id})
        return HttpResponse(status=200)
    except Exception:
        logger.exception("Unhandled webhook error", extra={"order_id": order_id})
        return HttpResponse(status=200)


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    security=[{"Bearer": []}],
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["razorpay_order_id"],
        properties={
            "razorpay_order_id": openapi.Schema(type=openapi.TYPE_STRING),
            "razorpay_payment_id": openapi.Schema(type=openapi.TYPE_STRING),
        },
        example=PAYMENT_FAILED_REQUEST_EXAMPLE,
    ),
    operation_description="Mark student payment as failed from frontend fallback callback.",
    responses={
        200: "Failure recorded.",
        400: "Missing order id.",
        401: "Authentication credentials were not provided.",
        403: "Student role required.",
        404: "Payment not found.",
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsStudent])
def payment_failed(request):
    order_id = request.data.get("razorpay_order_id")
    payment_id = request.data.get("razorpay_payment_id")

    if not order_id:
        return Response({"error": "Missing razorpay_order_id"}, status=status.HTTP_400_BAD_REQUEST)

    payment = StudentPayment.objects.filter(
        razorpay_order_id=order_id,
        student=request.user,
    ).first()
    if not payment:
        return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

    if payment.status != StudentPayment.STATUS_SUCCESS:
        payment.status = StudentPayment.STATUS_FAILED
        payment.razorpay_payment_id = payment_id
        payment.save(update_fields=["status", "razorpay_payment_id", "updated_at"])

        if not PaymentHistory.objects.filter(razorpay_payment_id=payment_id).exists():
            PaymentHistory.objects.create(
                user=request.user,
                amount=payment.amount / 100,
                payment_method="unknown",
                payment_status="failed",
                razorpay_payment_id=payment_id,
                payment_details="Frontend failure callback",
            )

    return Response({"message": "Failure recorded"}, status=status.HTTP_200_OK)


def payment_test_page(request):
    return render(request, "payments/payment_page.html")


class PaymentHistoryListView(ListAPIView):
    queryset = PaymentHistory.objects.all().order_by("-registration_date")
    serializer_class = PaymentHistorySerializer
    pagination_class = PaymentPagination
    permission_classes = [IsAdminUser]


class StudentSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Payments"],
        responses={
            200: openapi.Response(
                description="Subscription summary for authenticated student.",
                examples={
                    "application/json": {
                        "is_paid": True,
                        "status": "ACTIVE",
                        "registration_number": "CRTD2026000001",
                        "payment_date": "2026-04-13",
                        "expiry_date": "2026-10-13",
                        "days_remaining": 183,
                    }
                },
            ),
            401: "Authentication credentials were not provided.",
            403: "Student role required.",
        },
        operation_description="Return current student payment/subscription status.",
    )
    def get(self, request):
        return Response(build_subscription_summary(request.user), status=status.HTTP_200_OK)
