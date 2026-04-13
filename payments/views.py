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
from .models import PaymentHistory,StudentSubscription,Payment
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
    # if not request.user.profile_completed:
    #     return Response({"error": "Complete profile first"}, status=400)
    

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


#wel will comment out  this when for the deployment for the future because the webhook is required for the production and the payment status registration number is handled by the webhook itself not by the verify payment 
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




            #---------------------------
            # remove this section for the production once the webhook is working fine

            from dateutil.relativedelta import relativedelta

            subscription = StudentSubscription.objects.filter(student=payment.user).first()

            if not subscription:
                subscription = StudentSubscription.objects.create(
                    student=payment.user,
                    payment=payment,
                    )

            # 🔥 Generate registration number (ONLY ONCE)
            if not subscription.registration_number:
                reg_no = generate_registration_number()
                subscription.registration_number = reg_no
                logger.info(f"🔥 Generated Registration: {reg_no}")

            today = date.today()

            subscription.payment = payment

            subscription.status = "ACTIVE"

            subscription.payment_date = today

            # ✅ SAFE DURATION LOGIC
            duration = payment.plan.duration_months if payment.plan else 6

            subscription.expiry_date = today + relativedelta(
                months=duration
                )

            subscription.save()

            logger.info("🔥 Subscription ACTIVATED")


            #_______________________

            
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

    



""""
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Verify Razorpay payment signature (light fallback).",
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
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
        # ✅ Only verify signature (NO business logic here)
        client.utility.verify_payment_signature(params)

        return Response({
            "message": "Payment verified (awaiting webhook confirmation)"
        })

    except razorpay.errors.SignatureVerificationError:
        return Response({"error": "Payment verification failed"}, status=400)

    except Exception as e:
        logger.error(f"Verify error: {str(e)}")
        return Response({"error": "Internal server error"}, status=500)

# #we will make this comment out  and the verify payment old method for the production process 
# # #Razorpay webhook to handle the payment status
@swagger_auto_schema(
    method="post",
    tags=["Payments"],
    operation_description="Handle Razorpay webhook events and update payment + subscription.",
)
@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_exempt
def razorpay_webhook(request):
    print("🔥 WEBHOOK HIT")

    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    # 🔐 Step 1: Verify webhook signature
    razorpay_client = get_razorpay_client()

    try:
        razorpay_client.utility.verify_webhook_signature(
            payload, signature, settings.RAZORPAY_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"❌ Invalid webhook signature: {str(e)}")
        return HttpResponse(status=400)

    data = json.loads(payload)
    event = data.get("event")

    # ================================
    # ✅ PAYMENT SUCCESS
    # ================================
    if event == "payment.captured":
        try:
            entity = data["payload"]["payment"]["entity"]
            order_id = entity["order_id"]
            payment_id = entity["id"]

            logger.info(f"✅ Payment Captured: {order_id}")

            with transaction.atomic():

                payment = Payment.objects.select_for_update().get(
                    razorpay_order_id=order_id
                )

                # 🔁 Idempotency check
                if payment.status == "paid":
                    logger.info("⚠️ Payment already processed")
                    return HttpResponse(status=200)

                # ✅ Update payment
                payment.status = "paid"
                payment.razorpay_payment_id = payment_id
                payment.save()

                logger.info("✅ Payment marked as paid")

                # ================================
                # 🔥 SUBSCRIPTION LOGIC
                # ================================
                from dateutil.relativedelta import relativedelta

                subscription = StudentSubscription.objects.filter(
                    student=payment.user
                ).first()

                if not subscription:
                    subscription = StudentSubscription.objects.create(
                        student=payment.user,
                        payment=payment
                    )

                # 🔥 Generate registration number (ONLY ONCE)
                if not subscription.registration_number:
                    reg_no = generate_registration_number()
                    subscription.registration_number = reg_no
                    logger.info(f"🔥 Generated Registration: {reg_no}")

                today = date.today()

                subscription.payment = payment
                subscription.status = "ACTIVE"
                subscription.payment_date = today
                # ✅ SAFE DURATION LOGIC
                duration = payment.plan.duration_months if payment.plan else 6

                subscription.expiry_date = today + relativedelta(
                    months=duration
                )

                subscription.save()

                logger.info("🔥 Subscription ACTIVATED")


                 # ================================
                # 📜 PAYMENT HISTORY
                # ================================
                if not PaymentHistory.objects.filter(
                    razorpay_payment_id=payment_id
                ).exists():

                    method = entity.get("method", "unknown")

                    PaymentHistory.objects.create(
                        payment=payment,
                        user=payment.user,
                        amount=payment.amount / 100,
                        payment_method=method,
                        payment_status="completed",
                        razorpay_payment_id=payment_id,
                        payment_details=f"Subscription Plan: {payment.plan.name if payment.plan else 'N/A'}"
                    )

        except Payment.DoesNotExist:
            logger.warning(f"⚠️ Payment not found: {order_id}")
            return HttpResponse(status=404)

        except Exception as e:
            logger.error(f"❌ Webhook error: {str(e)}")
            return HttpResponse(status=500)


    # ================================
    # ❌ PAYMENT FAILED
    # ================================
    elif event == "payment.failed":
        try:
            entity = data["payload"]["payment"]["entity"]
            order_id = entity["order_id"]
            payment_id = entity.get("id")

            logger.info(f"❌ Payment Failed: {order_id}")

            payment = Payment.objects.filter(
                razorpay_order_id=order_id
            ).first()

            if payment and payment.status != "paid":
                payment.status = "failed"
                payment.razorpay_payment_id = payment_id
                payment.save()

                logger.info("❌ Payment marked as failed")

        except Exception as e:
            logger.error(f"❌ Error processing payment.failed: {str(e)}")

    return HttpResponse(status=200)
"""


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