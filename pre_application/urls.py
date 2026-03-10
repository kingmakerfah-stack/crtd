from django.urls import path
from .views import PreApplicationCreateView , CreateReferralAPIView,CheckReferralCodeAPIView, PreApplicationListView

urlpatterns = [
    path('submit-form/', PreApplicationCreateView.as_view(), name='pre-application-create'),
    path('referral/create/<int:pk>/', CreateReferralAPIView.as_view(), name='create-referral'),
    path('referral/check/<str:code>/', CheckReferralCodeAPIView.as_view(), name='check-referral'),
    path("list/", PreApplicationListView.as_view(), name="pre-application-list"),
]