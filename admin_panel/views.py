from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import AdminRegisterSerializer
from rest_framework.permissions import AllowAny
from drf_yasg.utils import swagger_auto_schema


class AdminRegisterView(APIView):

    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=AdminRegisterSerializer)
    def post(self, request):
        serializer = AdminRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()

            return Response(
                {"message": "Admin registered successfully."},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)