from django.urls import path

from .views import SubscriptionPlanAPIView


urlpatterns = [
    path('plan/', SubscriptionPlanAPIView.as_view(), name='subscription-plan'),
]