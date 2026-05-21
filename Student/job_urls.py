from django.urls import path

from .views import (
    StudentApplicationHistoryAPIView,
    StudentJobApplyAPIView,
    StudentJobListAPIView,
)


urlpatterns = [
    path("jobs/", StudentJobListAPIView.as_view(), name="student-jobs"),
    path("jobs/<int:job_id>/apply/", StudentJobApplyAPIView.as_view(), name="student-job-apply"),
    path("applications/", StudentApplicationHistoryAPIView.as_view(), name="student-applications"),
]
