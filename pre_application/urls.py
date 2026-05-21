from django.urls import path

from .views import (
    ArchivePreApplicationAPIView,
    ArchivePreApplicationByEnquiryTokenAPIView,
    CheckReferralCodeAPIView,
    CreateReferralAPIView,
    CreateReferralByEnquiryTokenAPIView,
    PreApplicationListAPIView,
    PreApplicationLookupAPIView,
    PreApplicationByEnquiryTokenAPIView,
    PreApplicationCreateView,
    RestorePreApplicationAPIView,
    RestorePreApplicationByEnquiryTokenAPIView,
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
    path(
        "archive/enquiry/<str:enquiry_token>/",
        ArchivePreApplicationByEnquiryTokenAPIView.as_view(),
        name="archive-pre-application-by-enquiry-token",
    ),
    path(
        "archive/<int:pk>/",
        ArchivePreApplicationAPIView.as_view(),
        name="archive-pre-application",
    ),
    path(
        "restore/enquiry/<str:enquiry_token>/",
        RestorePreApplicationByEnquiryTokenAPIView.as_view(),
        name="restore-pre-application-by-enquiry-token",
    ),
    path(
        "restore/<int:pk>/",
        RestorePreApplicationAPIView.as_view(),
        name="restore-pre-application",
    ),
    path("referral/check/<str:code>/", CheckReferralCodeAPIView.as_view(), name="check-referral"),
]
