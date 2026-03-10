from django.shortcuts import render

# Create your views here.
from django.utils.timezone import now
from django.db.models import Count, Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from admin_analytics.serializers import ReferenceCodeStatusSerializer
from pre_application.models import PreApplication, ReferalCode
from .permissions import IsAdminRole


class EnquiryAnalyticsView(APIView):

    permission_classes = [IsAuthenticated,IsAdminRole]
    @swagger_auto_schema(security=[{"Bearer": []}])
    def get(self, request):

        analytics = PreApplication.objects.aggregate(
            total_enquiry_received=Count("id"),
            today_received=Count(
                "id",
                filter=Q(created_at__date=now().date())
            ),
        )

        enquiry_done = ReferalCode.objects.count()

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
    
class ReferenceCodeStatusView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        # Dashboard Stats
        total_reference_code = ReferalCode.objects.count()

        account_not_created = ReferalCode.objects.filter(is_used=False).count()

        registration_not_completed = ReferalCode.objects.filter(is_used=True).count()
        # Table Data
        queryset = ReferalCode.objects.select_related("student").all()

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": obj.student.name,
                "email": obj.student.email,
                "whatsapp": obj.student.whatsapp,
                "reference_code": obj.code,
                "status": "Used" if obj.is_used else "Not Used"
            })

        serializer = ReferenceCodeStatusSerializer(data, many=True)

        return Response({
            "stats": {
                "total_reference_code": total_reference_code,
                "account_not_created": account_not_created,
                "registration_not_completed": registration_not_completed
            },
            "results": serializer.data
        })    