from django.urls import path

from .views import (
    CheckReferralCodeAPIView,
    CreateReferralAPIView,
    CreateReferralByEnquiryTokenAPIView,
    PreApplicationListAPIView,
    PreApplicationLookupAPIView,
    PreApplicationByEnquiryTokenAPIView,
    PreApplicationCreateView,
)

urlpatterns = [
    path("submit-form/", PreApplicationCreateView.as_view(), name="pre-application-create"),
    path("admin/list/", PreApplicationListAPIView.as_view(), name="pre-application-list"),
    path("admin/lookup/", PreApplicationLookupAPIView.as_view(), name="pre-application-lookup"),
    path(
        "enquiry/<str:enquiry_token>/",
        PreApplicationByEnquiryTokenAPIView.as_view(),
        name="pre-application-by-enquiry-token",
    ),
    path(
        "referral/generate/<str:enquiry_token>/",
        CreateReferralByEnquiryTokenAPIView.as_view(),
        name="create-referral-by-enquiry-token",
    ),
    path(
        "referral/create/<int:pk>/",
        CreateReferralAPIView.as_view(),
        name="create-referral",
    ),
    path("referral/check/<str:code>/", CheckReferralCodeAPIView.as_view(), name="check-referral"),
]
