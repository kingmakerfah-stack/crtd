from datetime import date
import json
import hmac
import hashlib


from django.conf import settings
from django.contrib.auth import get_user_model


from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import render
from drf_yasg.utils import swagger_auto_schema
import razorpay 

from .services import create_razorpay_order, get_razorpay_client
from django.db import transaction
from .utils import expire_old_payments, generate_registration_number
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from .models import PaymentHistory,StudentPayment,StudentSubscription,Payment
from .serializers import PaymentHistorySerializer
from .pagination import PaymentPagination
from rest_framework.permissions import IsAdminUser
from django.utils import timezone
from subscription.models import SubscriptionPlan
from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator
import logging
logger = logging.getLogger(__name__)

User = get_user_model()


@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Create a Razorpay order for subscription payment.",
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
# @permission_classes([AllowAny])
def create_order(request):

    expire_old_payments() 

    # amount = 50000  # ₹500 in paise

    # get the current user if not then temp user for testing
    
    
    user = request.user
    # user =User.objects.first() 
    # #for testing the payment flow without authentication and then we will change it to the authenticated user in the future

    if not user:
        return Response({"error": "No user found in database"}, status=400)
    #  Check active subscription FIRST (before creating order)
    

    existing_payment = Payment.objects.filter(
    user=user,
    status="paid",
    subscription_end__gt=timezone.now()
).first()

    if existing_payment:
        return Response({
            "error": "Active subscription already exists"
        }, status=400)
    
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
    

    #  Always create new payment (NO get_or_create)
    Payment.objects.create(
        user=user,
        plan=plan,
        razorpay_order_id=order["id"],
        amount=amount,
        status="created"
    )

    

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
@csrf_exempt
@api_view(["POST"])
# @permission_classes([AllowAny])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    # data = request.data

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
        with transaction.atomic():
            payment=Payment.objects.select_for_update().get(
                razorpay_order_id=order_id
            )

            # Prevent duplicate processing
            if payment.status == "paid":
                return Response({"message":"Payment already processed"
                })
            # Prevent multiple active subscriptions for the same user
            existing_paid = Payment.objects.filter(
                user=payment.user,
                status="paid",
                subscription_end__gt=timezone.now()
            ).exclude(id=payment.id).exists()
            

            if existing_paid:
                return Response({
                    "error": "Active subscription already exists"
                }, status=400)
            
            payment_details = client.payment.fetch(payment_id)
            method = payment_details.get("method", "unknown")
            
            # ✅ Save payment details
            payment.razorpay_payment_id = payment_id
            payment.razorpay_signature = signature
            payment.activate_subscription()

            
            # payment.save()

            # ✅ Prevent duplicate history
            if not PaymentHistory.objects.filter(
                razorpay_payment_id=payment_id
            ).exists():


            
            # create the payment history record for the successful payment andsave the details in the payment history model for the admin to view the payment history in the admin panel
                PaymentHistory.objects.create(
                    payment=payment,
                    user=payment.user,
                    amount=payment.amount / 100,
                    payment_method=method,
                    payment_status="completed",
                    razorpay_payment_id=payment_id,
                    payment_details=f"Subscription Plan: {payment.plan.name if payment.plan else 'N/A'}"
                )

                # print("AFTER ACTIVATION:", payment.status, payment.subscription_end)
                logger.info(f"Payment activated for order {order_id}")

        return Response({
            "message": "Payment verified successfully",
            "subscription_active": payment.is_active()
        })

    except Payment.DoesNotExist:
        return Response({"error": "Payment record not found"}, status=404)

    except razorpay.errors.SignatureVerificationError:
        if payment_id:

            PaymentHistory.objects.create(
                user=request.user,
                amount=0,
                payment_method="unknown",
                payment_status="failed",
                razorpay_payment_id=payment_id,  # if available
                payment_details="Signature verification failed"
            )
        return Response(
            {"error": "Payment verification failed"},
            status=400
        )
    
    

    except Exception as e:
        logger.error(f"Payment error: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)

    



# # Razorpay Webhook
# @swagger_auto_schema(
#     method="post",
#     tags=["Payments"],
#     operation_description="Handle Razorpay webhook events and update payment status.",
# )
# @api_view(["POST"])
# @permission_classes([AllowAny])
# def razorpay_webhook(request):

#     body = request.body
#     signature = request.headers.get("X-Razorpay-Signature")

#     if not signature:
#         return Response({"error": "Signature missing"}, status=400)
    
#     #  Verify webhook signature
#     generated_signature = hmac.new(
#         settings.RAZORPAY_WEBHOOK_SECRET.encode(),
#         body,
#         hashlib.sha256
#     ).hexdigest()

#     # Verify webhook authenticity
#     if not hmac.compare_digest(generated_signature, signature):
#         return Response({"error": "Invalid signature"}, status=400)

#     data = json.loads(body)
#     event = data.get("event")

#     try:
#         with transaction.atomic():

#             payment_entity = data["payload"]["payment"]["entity"]
#             payment_id = payment_entity.get("id")
#             order_id = payment_entity.get("order_id")
#             method = payment_entity.get("method", "unknown")

#             payment = Payment.objects.select_for_update().filter(razorpay_order_id=order_id).first()

#             if not payment:
#                 return Response({"error": "Payment not found"}, status=404)

            
#             # SUCCESS CASE
            
#             if event == "payment.captured":

#                 if payment.status != "paid":
#                     payment.razorpay_payment_id = payment_id
#                     payment.activate_subscription()
#                     # return Response({"message": "Already processed"})

#                 if not PaymentHistory.objects.filter(
#                     razorpay_payment_id=payment_id
#                 ).exists():

                

#                     PaymentHistory.objects.create(
#                         payment=payment,
#                         user=payment.user,
#                         amount=payment.amount / 100,
#                         payment_method=method,
#                         payment_status="completed",
#                         razorpay_payment_id=payment_id,
#                         payment_details="Webhook success"
#                     )

            
#             #  FAILURE CASE
            
#             elif event == "payment.failed":

#                 #  Only update if not already successful
#                 if payment.status != "paid":
#                     payment.status = "failed"
#                     payment.razorpay_payment_id = payment_id
#                     payment.save()

#                 #  Always log failure (but avoid duplicate)
#                 if not PaymentHistory.objects.filter(
#                     razorpay_payment_id=payment_id
#                 ).exists():

#                     PaymentHistory.objects.create(
#                         payment=payment,
#                         user=payment.user,
#                         amount=payment.amount / 100,
#                         payment_method=method,
#                         payment_status="failed",
#                         razorpay_payment_id=payment_id,
#                         payment_details="Webhook failure"
#                     )


#     except Payment.DoesNotExist:
#         return Response({"error": "Payment not found"}, status=404)

#     return Response({"status": "Webhook processed"})




#  Razorpay Webhook
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Handle Razorpay webhook events and update payment status.",
)
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_exempt
def razorpay_webhook(request):
    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    # 🔐 Step 1: Verify signature
    try:
        razorpay_client.utility.verify_webhook_signature(
            payload, signature, settings.RAZORPAY_WEBHOOK_SECRET
        )
    except Exception as e:
        print("❌ Invalid signature:", str(e))
        return HttpResponse(status=400)

    data = json.loads(payload)
    event = data.get("event")

    # Only handle relevant events
    if event == "payment.captured":
        entity = data["payload"]["payment"]["entity"]
        order_id = entity["order_id"]
        payment_id = entity["id"]

        print("✅ Payment Captured:", order_id)

        # ================================
        # 🔵 OLD PAYMENT FLOW
        # ================================
        try:
            old_payment = Payment.objects.get(razorpay_order_id=order_id)

            if old_payment.status != "SUCCESS":
                old_payment.status = "SUCCESS"
                old_payment.razorpay_payment_id = payment_id
                old_payment.save()

                print("✅ Old payment updated")

        except Payment.DoesNotExist:
            print("ℹ️ Not an old payment")

        # ================================
        # 🟢 NEW STUDENT FLOW
        # ================================
        try:
            student_payment = StudentPayment.objects.select_for_update().get(
                razorpay_order_id=order_id
            )

            if student_payment.status == "SUCCESS":
                return HttpResponse(status=200)  # idempotent

            student_payment.status = "SUCCESS"
            student_payment.razorpay_payment_id = payment_id
            student_payment.save()

            from .utils import generate_registration_number
            from datetime import date
            from dateutil.relativedelta import relativedelta

            subscription, _ = StudentSubscription.objects.get_or_create(
                student=student_payment.student
            )

            if not subscription.registration_number:
                subscription.registration_number = generate_registration_number()

            today = date.today()

            subscription.payment = student_payment
            subscription.status = "ACTIVE"
            subscription.payment_date = today
            subscription.expiry_date = today + relativedelta(
                months=settings.SUBSCRIPTION_DURATION_MONTHS
            )
            subscription.save()

            print("✅ Student subscription activated")

        except StudentPayment.DoesNotExist:
            print("ℹ️ Not a student payment")

    # ================================
    # ❌ HANDLE FAILURE
    # ================================
    elif event == "payment.failed":
        entity = data["payload"]["payment"]["entity"]
        order_id = entity["order_id"]

        print("❌ Payment Failed:", order_id)

        # OLD
        try:
            old_payment = Payment.objects.get(razorpay_order_id=order_id)
            old_payment.status = "FAILED"
            old_payment.save()
        except Payment.DoesNotExist:
            pass

        # NEW
        try:
            student_payment = StudentPayment.objects.get(
                razorpay_order_id=order_id
            )
            student_payment.status = "FAILED"
            student_payment.save()
        except StudentPayment.DoesNotExist:
            pass

    return HttpResponse(status=200)



#views for the payment failure
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Handle payment failure from frontend and update payment status.",
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def payment_failed(request):

    order_id = request.data.get("razorpay_order_id")
    payment_id = request.data.get("razorpay_payment_id")

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)

        if payment.status != "paid":
            payment.status = "failed"
            payment.razorpay_payment_id = payment_id
            payment.save()

            PaymentHistory.objects.create(
                payment=payment,
                user=payment.user,
                amount=payment.amount / 100,
                payment_method="unknown",
                payment_status="failed",
                razorpay_payment_id=payment_id,
                payment_details="Frontend failure"
            )

        return Response({"message": "Failure recorded"})

    except Payment.DoesNotExist:
        return Response({"error": "Payment not found"}, status=404)
    

# from django.shortcuts import render

def payment_test_page(request):
    return render(request, "payments/payment_page.html")


#payment history view  for admin to view all payment history with pagination

class PaymentHistoryListView(ListAPIView):

    queryset = PaymentHistory.objects.all().order_by("-registration_date")

    serializer_class = PaymentHistorySerializer

    pagination_class = PaymentPagination

    permission_classes = [IsAdminUser]
    # permission_classes = [AllowAny]




# CREATE STUDENT PAYMENT INITIATE API

# @api_view(["POST"])
class StudentPaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]


    def post(self, request):
        user = request.user

        if not user.profile_completed:
            return Response({"error": "Complete profile first"}, status=400)

        if StudentSubscription.objects.filter(student=user, status="ACTIVE").exists():
            return Response({"error": "Already subscribed"}, status=400)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount": settings.SUBSCRIPTION_AMOUNT_PAISE,
            "currency": "INR",
            "payment_capture": 1
        })

        StudentPayment.objects.create(
            student=user,
            razorpay_order_id=order["id"],
            amount=settings.SUBSCRIPTION_AMOUNT_PAISE
        )

        return Response({
            "order_id": order["id"],
            "amount": settings.SUBSCRIPTION_AMOUNT_PAISE,
            "key": settings.RAZORPAY_KEY_ID
        })
    

# #CREATE WEBHOOK FOR THE STUDENT PAYMENT AND SUBSCRIPTION ACTIVATION

# @csrf_exempt
# def student_payment_webhook(request):
#     payload = request.body
#     signature = request.headers.get("X-Razorpay-Signature")

#     try:
#         razorpay_client.utility.verify_webhook_signature(
#             payload, signature, settings.RAZORPAY_WEBHOOK_SECRET
#         )
#     except:
#         return HttpResponse(status=400)

#     data = json.loads(payload)

#     if data["event"] == "payment.captured":
#         entity = data["payload"]["payment"]["entity"]

#         order_id = entity["order_id"]
#         payment_id = entity["id"]

#         payment = StudentPayment.objects.select_for_update().get(
#             razorpay_order_id=order_id
#         )

#         if payment.status == "SUCCESS":
#             return HttpResponse(status=200)

#         payment.status = "SUCCESS"
#         payment.razorpay_payment_id = payment_id
#         payment.save()

#         subscription, _ = StudentSubscription.objects.get_or_create(
#             student=payment.student
#         )

#         if not subscription.registration_number:
#             subscription.registration_number = generate_registration_number()

#         today = date.today()

#         subscription.payment = payment
#         subscription.status = "ACTIVE"
#         subscription.payment_date = today
#         subscription.expiry_date = today + relativedelta(
#             months=settings.SUBSCRIPTION_DURATION_MONTHS
#         )
#         subscription.save()

#     return HttpResponse(status=200)


# CREATE SUBSCRIPTION API

class StudentSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    

    def get(self, request):
        try:
            sub = StudentSubscription.objects.get(student=request.user)

            return Response({
                "is_paid": sub.status == "ACTIVE",
                "registration_number": sub.registration_number,
                "expiry_date": sub.expiry_date
            })

        except StudentSubscription.DoesNotExist:
            return Response({
                "is_paid": False,
                "registration_number": None
            })