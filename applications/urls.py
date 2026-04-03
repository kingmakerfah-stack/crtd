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
    path("student/my-applications/",StudentApplicationListView.as_view()),


    path("admin/cooling-period/update/",CoolDownUpdateView.as_view(),name="cooldown-days-update"),

    path("admin/job-summary/",JobWiseSummaryView.as_view()),

    path("admin/job/<int:job_id>/", JobApplicationsView.as_view()),

    path("admin/job/status/<int:id>",ApplicationDetailView.as_view()),

    path("admin/update-status/<int:id>/",UpdateApplicationStatusView.as_view()),
    
    path("admin/dashboard/summary/",RealTimeActivitySummaryView.as_view()),
    path("admin/update-cooldown/<int:id>/",UpdateStudentCoolDownView.as_view())

    
]
