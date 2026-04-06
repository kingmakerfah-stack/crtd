from django.shortcuts import render

# Create your views here.
from django.utils.timezone import now
from django.db.models import Count, Q,Sum
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated,AllowAny
from drf_yasg.utils import swagger_auto_schema
from admin_analytics.models import Testimonial,CompanyPartners
from admin_analytics.pagination import TestimonialPagination
from admin_analytics.serializers import ReferenceCodeStatusSerializer
from pre_application.models import PreApplication, ReferalCode
from .permissions import IsAdminRole
from datetime import timedelta
from payments.models import Payment
from jobs.models import Job
from .serializers import UpdateReferenceStatusSerializer, TestimonialSerializer,CompanyPartnersSerializer

class EnquiryAnalyticsView(APIView):

    permission_classes = [IsAuthenticated,IsAdminRole]
    @swagger_auto_schema(security=[{"Bearer": []}])
    def get(self, request):

        analytics = PreApplication.objects.filter(is_deleted=False).aggregate(
            total_enquiry_received=Count("id"),
            today_received=Count(
                "id",
                filter=Q(created_at__date=now().date())
            ),
        )

        enquiry_done = ReferalCode.objects.filter(student__is_deleted=False).count()

        pending_enquiry = max(
            analytics["total_enquiry_received"] - enquiry_done,
            0
        )

        data = {
            "total_enquiry_received": analytics["total_enquiry_received"],
            "today_received": analytics["today_received"],
            "enquiry_done": enquiry_done,
            "pending_enquiry": pending_enquiry,
        }

        return Response(data)


class EnquiryTableView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        enquiries = PreApplication.objects.filter(is_deleted=False)

        data = []

        for i, obj in enumerate(enquiries, start=1):
            data.append({
                "s_no": i,
                "enquiry_token": obj.enquiry_token,
                "date_time": obj.created_at.strftime("%b %d, %Y at %I:%M%p").lower(),
                "full_name": f"{obj.first_name} {obj.last_name}",
                "email": obj.email,
                "whatsapp": obj.whatsapp_no,
                "alternate_phone": obj.alternate_phone,
                "birthplace": obj.birthplace_state
            })

        return Response(data)
        
class ReferenceCodeStatusView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        total_reference_code = ReferalCode.objects.filter(student__is_deleted=False).count()

        account_not_created = ReferalCode.objects.filter(
            status="not_used",
            student__is_deleted=False,
        ).count()

        membership_not_completed = ReferalCode.objects.filter(
            status="membership_pending",
            student__is_deleted=False,
        ).count()

        queryset = ReferalCode.objects.select_related("student").filter(student__is_deleted=False)

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": f"{obj.student.first_name} {obj.student.last_name}",
                "email": obj.student.email,
                "whatsapp": obj.student.whatsapp_no,
                "reference_code": obj.code,
                "status": obj.get_status_display()
            })

        serializer = ReferenceCodeStatusSerializer(data, many=True)

        return Response({
            "stats": {
                "total_reference_code": total_reference_code,
                "account_not_created": account_not_created,
                "membership_not_completed": membership_not_completed
            },
            "results": serializer.data
        })

class UpdateReferenceStatusView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    @swagger_auto_schema(request_body=UpdateReferenceStatusSerializer)
    def patch(self, request, pk):

        try:
            ref = ReferalCode.objects.get(id=pk)
        except ReferalCode.DoesNotExist:
            return Response({"error": "Reference code not found"}, status=404)

        serializer = UpdateReferenceStatusSerializer(data=request.data)

        if serializer.is_valid():
            if ref.student.is_deleted:
                return Response(
                    {"error": "Cannot update reference status for archived pre-application"},
                    status=400,
                )

            ref.status = serializer.validated_data["status"]
            ref.save()

            return Response({
                "message": "Status updated successfully"
            })

        return Response(serializer.errors, status=400)
class DeleteReferenceCodeView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk):

        try:
            ref = ReferalCode.objects.get(id=pk)
        except ReferalCode.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        ref.delete()

        return Response({"message": "Reference code deleted"})  

# Admin payment analytics view to calculate revenue
class PaymentAnalyticsView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        today = now().date()
        week_start = today - timedelta(days=today.weekday())

        analytics = Payment.objects.aggregate(

            # Today
            today_revenue=Sum(
                "amount",
                filter=Q(status="paid", created_at__date=today)
            ),
            today_transactions=Count(
                "id",
                filter=Q(status="paid", created_at__date=today)
            ),

            # Week
            week_revenue=Sum(
                "amount",
                filter=Q(status="paid", created_at__date__gte=week_start)
            ),
            week_transactions=Count(
                "id",
                filter=Q(status="paid", created_at__date__gte=week_start)
            ),

            # Month
            month_revenue=Sum(
                "amount",
                filter=Q(
                    status="paid",
                    created_at__month=today.month,
                    created_at__year=today.year
                )
            ),
            month_transactions=Count(
                "id",
                filter=Q(
                    status="paid",
                    created_at__month=today.month,
                    created_at__year=today.year
                )
            ),

            # Year
            year_revenue=Sum(
                "amount",
                filter=Q(status="paid", created_at__year=today.year)
            ),
            year_transactions=Count(
                "id",
                filter=Q(status="paid", created_at__year=today.year)
            ),

            # Total
            total_revenue=Sum(
                "amount",
                filter=Q(status="paid")
            ),
            total_transactions=Count(
                "id",
                filter=Q(status="paid")
            ),
        )
        data = {
            "today_revenue": (analytics["today_revenue"] or 0) / 100,
            "today_transactions": analytics["today_transactions"] or 0,

            "week_revenue": (analytics["week_revenue"] or 0) / 100,
            "week_transactions": analytics["week_transactions"] or 0,

            "month_revenue": (analytics["month_revenue"] or 0) / 100,
            "month_transactions": analytics["month_transactions"] or 0,

            "year_revenue": (analytics["year_revenue"] or 0) / 100,
            "year_transactions": analytics["year_transactions"] or 0,

            "total_revenue": (analytics["total_revenue"] or 0) / 100,
            "total_transactions": analytics["total_transactions"] or 0,
        }
        return Response(data)

class CreateTestimonialView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    @swagger_auto_schema(request_body=TestimonialSerializer)
    def post(self, request):

        serializer = TestimonialSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                {"message": "Testimonial created successfully"},
                status=201
            )

        return Response(serializer.errors, status=400) 

class TestimonialListView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        queryset = Testimonial.objects.all().order_by("-created_at")

        paginator = TestimonialPagination()
        page = paginator.paginate_queryset(queryset, request)

        serializer = TestimonialSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data) 

class UpdateTestimonialView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    @swagger_auto_schema(request_body=TestimonialSerializer)
    def patch(self, request, pk):

        try:
            testimonial = Testimonial.objects.get(id=pk)
        except Testimonial.DoesNotExist:
            return Response(
                {"error": "Testimonial not found"},
                status=404
            )

        serializer = TestimonialSerializer(
            testimonial,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()

            return Response({
                "message": "Testimonial updated successfully"
            })

        return Response(serializer.errors, status=400)

class DeleteTestimonialView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk):

        try:
            testimonial = Testimonial.objects.get(id=pk)
        except Testimonial.DoesNotExist:
            return Response(
                {"error": "Testimonial not found"},
                status=404
            )

        testimonial.delete()

        return Response({
            "message": "Testimonial deleted successfully"
        })
class UpdateCompanyPartnersView(APIView):
    permission_classes =[IsAuthenticated,IsAdminRole]
    
    @swagger_auto_schema(
        request_body=CompanyPartnersSerializer,
        operation_description = """ Update the total number of company partners.
        No ID is required for this endpoint."""
    )
    def put(self,request):
        partners,created = CompanyPartners.objects.get_or_create(id=1)
        serializer=CompanyPartnersSerializer(partners,data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message":"Company Partners Updated Successfully",
                         "data":serializer.data},
                        status=status.HTTP_200_OK)

class CollaborationAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated,IsAdminRole]
    @swagger_auto_schema(
            operation_description="Returns total company partners, job openings, and testimonials count"
    )
    def get(self,request):
        partners,_=CompanyPartners.objects.get_or_create(id=1)
        total_job_openings = Job.objects.count()
        testimonials = Testimonial.objects.count()
        
        data = {
            "total_partners": partners.total_partners,
            "total_job_openings" : total_job_openings,
            "testimonials":testimonials
        }
        return Response(data,status=status.HTTP_200_OK)