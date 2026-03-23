import json
import hmac
import hashlib

from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import render
from drf_yasg.utils import swagger_auto_schema
import razorpay 
from .models import Payment
from .services import create_razorpay_order, get_razorpay_client

User = get_user_model()


# # Create Order API
# @api_view(["POST"])
# @permission_classes([AllowAny])
# def create_order(request):

#     amount = 50000  # ₹500
    
#     order = create_razorpay_order(request.user.id, amount)

#     payment, created = Payment.objects.get_or_create(
#         user=request.user,
#         defaults={
#             "razorpay_order_id": order["id"],
#             "amount": amount
#         }
#     )

#     if not created:
#         payment.razorpay_order_id = order["id"]
#         payment.amount = amount
#         payment.save()

#     return Response({
#         "order_id": order["id"],
#         "amount": amount,
#         "key": settings.RAZORPAY_KEY_ID
#     })


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Create a Razorpay order for subscription payment.",
)
@api_view(["POST"])
# @permission_classes([IsAuthenticated])
@permission_classes([AllowAny])
def create_order(request):

    amount = 50000  # ₹500 in paise

    # TEMP user for testing
    user = User.objects.first()

    if not user:
        return Response({"error": "No user found in database"}, status=400)

    order = create_razorpay_order(user.id, amount)

    payment, created = Payment.objects.get_or_create(
        user=user,
        defaults={
            "razorpay_order_id": order["id"],
            "amount": amount
        }
    )

    if not created:
        payment.razorpay_order_id = order["id"]
        payment.amount = amount
        payment.save()

    return Response({
        "order_id": order["id"],
        "amount": amount,
        "key": settings.RAZORPAY_KEY_ID
    })


# Verify Payment
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Verify Razorpay payment signature and activate subscription.",
)
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_payment(request):

    client = get_razorpay_client()

    payment_id = request.data.get("razorpay_payment_id")
    order_id = request.data.get("razorpay_order_id")
    signature = request.data.get("razorpay_signature")

    if not payment_id or not order_id or not signature:
        return Response({"error": "Missing payment parameters"}, status=400)

    params = {
        "razorpay_payment_id": payment_id,
        "razorpay_order_id": order_id,
        "razorpay_signature": signature
    }

    try:
        # Verify signature from Razorpay
        client.utility.verify_payment_signature(params)

        payment = Payment.objects.get(razorpay_order_id=order_id)

        # Prevent duplicate processing
        if payment.status == "paid":
            return Response({
                "message": "Payment already processed"
            })

        payment.razorpay_payment_id = payment_id
        payment.activate_subscription()  # this also sets status="paid"

        return Response({
            "message": "Payment verified successfully",
            "subscription_active": payment.is_active()
        })

    except Payment.DoesNotExist:
        return Response({"error": "Payment record not found"}, status=404)

    except razorpay.errors.SignatureVerificationError:
        return Response(
            {"error": "Payment verification failed"},
            status=400
        )
    



# Razorpay Webhook
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Handle Razorpay webhook events and update payment status.",
)
@api_view(["POST"])
@permission_classes([AllowAny])
def razorpay_webhook(request):

    body = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        return Response({"error": "Signature missing"}, status=400)

    generated_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # Verify webhook authenticity
    if not hmac.compare_digest(generated_signature, signature):
        return Response({"error": "Invalid signature"}, status=400)

    data = json.loads(body)

    if data.get("event") == "payment.captured":

        payment_entity = data["payload"]["payment"]["entity"]
        payment_id = payment_entity["id"]
        order_id = payment_entity["order_id"]

        try:
            payment = Payment.objects.get(razorpay_order_id=order_id)

            # Prevent duplicate webhook execution
            if payment.status == "paid":
                return Response({"message": "Payment already processed"})

            payment.razorpay_payment_id = payment_id
            payment.activate_subscription()

        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found"}, status=404)

    return Response({"status": "Webhook processed"})


# from django.shortcuts import render

def payment_test_page(request):
    return render(request, "payments/payment_page.html")