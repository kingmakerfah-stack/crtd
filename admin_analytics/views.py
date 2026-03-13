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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import EnquiryAnalytics
from .serializers import EnquiryTableSerializer, UpdateReferenceStatusSerializer
from .permissions import IsAdminRole


from pre_application.models import PreApplication

class EnquiryTableView(APIView):

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):

        enquiries = PreApplication.objects.all()

        data = []

        for i, obj in enumerate(enquiries, start=1):
            data.append({
                "s_no": i,
                "enquiry_token": f"ENQ{100000 + obj.id}",
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

        total_reference_code = ReferalCode.objects.count()

        account_not_created = ReferalCode.objects.filter(
            status="not_used"
        ).count()

        membership_not_completed = ReferalCode.objects.filter(
            status="membership_pending"
        ).count()

        queryset = ReferalCode.objects.select_related("student").all()

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