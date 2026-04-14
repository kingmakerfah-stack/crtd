from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasModuleAccess, IsAdminPortalUser

from .models import SubscriptionPlan
from .serializers import SubscriptionPlanSerializer


class SubscriptionPlanAPIView(APIView):
    required_module = 'membership'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminPortalUser(), HasModuleAccess()]

    def get_object(self):
        plan = SubscriptionPlan.objects.filter(is_active=True).first()
        if not plan:
            raise NotFound('Active subscription plan not found.')
        return plan

    @swagger_auto_schema(
        security=[],
        tags=["Subscription"],
        responses={200: SubscriptionPlanSerializer, 404: 'Active subscription plan not found.'},
        operation_description='Return the active subscription plan. This endpoint is public.',
    )
    def get(self, request):
        serializer = SubscriptionPlanSerializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Subscription"],
        request_body=SubscriptionPlanSerializer,
        responses={201: SubscriptionPlanSerializer, 400: 'Validation error', 403: 'Admin access required.'},
        operation_description='Create the subscription plan. Admin only.',
    )
    def post(self, request):
        serializer = SubscriptionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Subscription"],
        request_body=SubscriptionPlanSerializer,
        responses={200: SubscriptionPlanSerializer, 400: 'Validation error', 403: 'Admin access required.', 404: 'Active subscription plan not found.'},
        operation_description='Fully update the subscription plan. Admin only.',
    )
    def put(self, request):
        plan = self.get_object()
        serializer = SubscriptionPlanSerializer(plan, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Subscription"],
        request_body=SubscriptionPlanSerializer,
        responses={200: SubscriptionPlanSerializer, 400: 'Validation error', 403: 'Admin access required.', 404: 'Active subscription plan not found.'},
        operation_description='Partially update the subscription plan. Admin only.',
    )
    def patch(self, request):
        plan = self.get_object()
        serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        security=[{"Bearer": []}],
        tags=["Subscription"],
        responses={204: 'Subscription plan deleted.', 403: 'Admin access required.', 404: 'Active subscription plan not found.'},
        operation_description='Delete the subscription plan. Admin only.',
    )
    def delete(self, request):
        plan = self.get_object()
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
