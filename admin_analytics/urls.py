from django.urls import path
from .views import EnquiryAnalyticsView, ReferenceCodeStatusView


urlpatterns = [
    path("enquiry-analytics/", EnquiryAnalyticsView.as_view()),
    path("reference-code-status/", ReferenceCodeStatusView.as_view()),
]