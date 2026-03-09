from django.urls import path
from .views import JobListView, JobUpdateView, JobCreateView

urlpatterns = [
    path("", JobListView.as_view(), name="job-list"),
    path("admin/", JobCreateView.as_view(), name="job-create"),
    path("admin/<int:pk>/", JobUpdateView.as_view(), name="job-manage"),
]