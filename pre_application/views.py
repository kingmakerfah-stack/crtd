from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import PreApplication
from .serializers import PreApplicationSerializer , ReferalCodeSerializer
from drf_yasg.utils import swagger_auto_schema
from utils.email_service import EmailService
from rest_framework.generics import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import ReferalCode
from rest_framework.permissions import AllowAny
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


@method_decorator(csrf_exempt, name='dispatch')
class CreateReferralAPIView(APIView):
    """
    Create a referral code for a pre-application and send approval email.
    
    When a referral code is successfully created, an approval email is
    automatically sent to the student using the EmailService.
    """

    def get(self, request, pk):
        """
        Generate a referral code for a student and send approval email.
        
        Args:
            pk: The primary key of the PreApplication instance
            
        Returns:
            201: Referral code created successfully with email sent
            400: Student already verified or validation error
            404: PreApplication not found
        """
        pre_app = get_object_or_404(PreApplication, pk=pk)

        # Prevent duplicate referral
        if pre_app.verified:
            return Response(
                {"error": "Referral already exists for this student"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReferalCodeSerializer(data={
            "student": pre_app.id
        })

        if serializer.is_valid():
            referral = serializer.save()
            
            # Mark the student as verified
            pre_app.verified = True
            pre_app.save()
            
            # Send approval email asynchronously
            context = {
                'first_name': pre_app.first_name,
                'reference_code': referral.code
            }
            EmailService.send_approval_email(pre_app.email, context)
            
            return Response(
                {
                    **serializer.data,
                    "message": "Referral code created and approval email sent"
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# referal code view to check if the referal code is valid or not and return the pre application details if valid

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


class CheckReferralCodeAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Validate referral code",
        description="Check if a referral code is valid and return associated pre-application details.",
        parameters=[
            OpenApiParameter(
                name="code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Referral code to validate",
                required=True,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Referral code is valid",
                response={
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "whatsapp_no": {"type": "string"},
                        "alternate_phone": {"type": "string"},
                    },
                },
            ),
            404: OpenApiResponse(description="Referral code not found"),
        },
    )
    def get(self, request, code):
        referral = get_object_or_404(ReferalCode, code=code)
        pre_app = referral.student

        return Response({
            "first_name": pre_app.first_name,
            "last_name": pre_app.last_name,
            "email": pre_app.email,
            "whatsapp_no": pre_app.whatsapp_no,
            "alternate_phone": pre_app.alternate_phone,
        }, status=status.HTTP_200_OK)