from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import PreApplication
from .serializers import PreApplicationSerializer , ReferalCodeSerializer
from drf_yasg.utils import swagger_auto_schema
class PreApplicationCreateView(APIView):
    @swagger_auto_schema(
        request_body=PreApplicationSerializer,
        responses={
            201: PreApplicationSerializer,
            400: "Validation Error"
        },
        operation_description="Create a new pre-application"
    )
    def post(self, request):
        serializer = PreApplicationSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReferalCodeCreateView(APIView):
    @swagger_auto_schema(
        request_body=ReferalCodeSerializer,
        responses={
            201: ReferalCodeSerializer,
            400: "Validation Error"
        },
        operation_description="Create a new referral code"
    )
    def post(self, request):
        serializer = ReferalCodeSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
from rest_framework.generics import get_object_or_404
from .serializers import ReferalCodeSerializer

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class CreateReferralAPIView(APIView):

    def get(self, request, pk):
        pre_app = get_object_or_404(PreApplication, pk=pk)

        # Optional: Prevent duplicate referral
        if pre_app.verified:
            return Response(
                {"error": "Referral already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReferalCodeSerializer(data={
            "student": pre_app.id   # adjust if field name differs
        })

        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)