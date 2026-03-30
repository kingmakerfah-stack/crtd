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



from rest_framework.generics import ListAPIView
from .models import PaymentHistory
from .serializers import PaymentHistorySerializer
from .pagination import PaymentPagination
from rest_framework.permissions import IsAdminUser
from subscription.models import SubscriptionPlan


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

    # amount = 50000  # ₹500 in paise

    # get the current user if not then temp user for testing
    
    
    # user = request.user
    user =User.objects.first() #for testing the payment flow without authentication and then we will change it to the authenticated user in the future

    if not user:
        return Response({"error": "No user found in database"}, status=400)
    
    #GET SUBSCRIPTION PLAN
    plan = SubscriptionPlan.objects.filter(is_active=True).first()

    if not plan:
        return Response({"error": "Subscription plan not found. Contact admin."}, status=404)
    
    #  CALCULATE FINAL PRICE (AFTER DISCOUNT)
    final_price = plan.final_price

    #  CONVERT TO PAISE (RAZORPAY FORMAT)
    amount = int(final_price * 100)

    # create the razorpay order
    order = create_razorpay_order(user.id, amount)

    #save payment with plan
    payment, created = Payment.objects.get_or_create(
        user=user,
        defaults={
            "razorpay_order_id": order["id"],
            "amount": amount
        }
    )

    if not created:
        payment.plan = plan
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
        payment.save()


        # create the payment history record for the successful payment andsave the details in the payment history model for the admin to view the payment history in the admin panel
        PaymentHistory.objects.create(
            user=payment.user,
            amount=payment.amount / 100,   # convert paise to rupees
            payment_method="upi",
            payment_status="completed",
            razorpay_payment_id=payment_id,
            payment_details=f"Subscription Plan: {payment.plan.name}"
        )

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



#payment history view  for admin to view all payment history with pagination

class PaymentHistoryListView(ListAPIView):

    queryset = PaymentHistory.objects.all().order_by("-registration_date")

    serializer_class = PaymentHistorySerializer

    pagination_class = PaymentPagination

    # permission_classes = [IsAdminUser]
    permission_classes = [AllowAny]
