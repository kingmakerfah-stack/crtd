from django.urls import path
from .views import (EnquiryAnalyticsView, 
                    ReferenceCodeStatusView, 
                    EnquiryTableView, 
                    UpdateReferenceStatusView,
                    DeleteReferenceCodeView,
                    PaymentAnalyticsView, 
                    UpdateCompanyPartnersView,
                    CollaborationAnalyticsAPIView)


urlpatterns = [
    path("enquiry-analytics/", EnquiryAnalyticsView.as_view()),
    path("enquiry-table/", EnquiryTableView.as_view()),
    path("reference-code-status/", ReferenceCodeStatusView.as_view()),

        # edit application status
    path(
        "reference-code/<int:pk>/update/",
        UpdateReferenceStatusView.as_view(),
        name="update-reference-status"),

        # delete reference code
    path(
        "reference-code/<int:pk>/delete/",
        DeleteReferenceCodeView.as_view(),
        name="delete-reference-code"
    ),    
    path('payments-analytics/',PaymentAnalyticsView.as_view()),

    path("company-partners/update/",UpdateCompanyPartnersView.as_view()),
    path("collaborations/",CollaborationAnalyticsAPIView.as_view())
]