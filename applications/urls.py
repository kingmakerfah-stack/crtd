from django.urls import path
from .views import (ApplyJobView,CoolDownUpdateView,JobWiseSummaryView,
                    JobApplicationsView,
                    UpdateApplicationStatusView,
                    RealTimeActivitySummaryView,
                    StudentApplicationListView,
                    UpdateStudentCoolDownView,
                    ApplicationDetailView)

urlpatterns = [
    path("apply-job/<int:id>/",ApplyJobView.as_view(),name="apply-job"),
    path("student/my-applications/",StudentApplicationListView.as_view(),name="student-applications-list"),


    path("admin/cooling-period/update/",CoolDownUpdateView.as_view(),name="cooldown-days-update"),

    path("admin/job-summary/",JobWiseSummaryView.as_view(),name="admin-job-summary"),

    path("admin/job/<int:job_id>/", JobApplicationsView.as_view(),name="admin-job-applications"),

    path("admin/job/status/<int:id>",ApplicationDetailView.as_view(),name="admin-application-detail"),

    path("admin/update-status/<int:id>/",UpdateApplicationStatusView.as_view(),name="admin-update-application-status"),
    
    path("admin/realtime/summary/",RealTimeActivitySummaryView.as_view(),name="admin-dashboard-summary"),
    path("admin/update-cooldown/<int:id>/",UpdateStudentCoolDownView.as_view(),name="admin-update-student-cooldown")

    
]
