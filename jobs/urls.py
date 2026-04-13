from django.urls import path

from .views import (
    JobListCreateView,
    JobDetailView,
    PublicTestimonialListView,
    AdminTestimonialListCreateView,
    AdminTestimonialDetailView,
)

urlpatterns = [
    path("", JobListCreateView.as_view(), name="job-list-create"),
    path("<int:pk>/", JobDetailView.as_view(), name="job-detail"),
    path("testimonials/", PublicTestimonialListView.as_view(), name="public-testimonial-list"),
    path("admin/testimonials/", AdminTestimonialListCreateView.as_view(), name="admin-testimonial-list-create"),
    path("admin/testimonials/<int:pk>/", AdminTestimonialDetailView.as_view(), name="admin-testimonial-detail"),
]
