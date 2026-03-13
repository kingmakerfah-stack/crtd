from django.urls import path
from .views import (EnquiryAnalyticsView, 
                    ReferenceCodeStatusView, 
                    EnquiryTableView, 
                    UpdateReferenceStatusView,
                    DeleteReferenceCodeView)


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
]