from django.urls import include, path
from .views import (
    StudentDataView,
    StudentPersonalDetails,
    StudentEducationView,
    StudentCareerPreferenceView,
)

urlpatterns = [
    # 🔹 Get complete student data (all sections)
    path("profile/", StudentDataView.as_view(), name="student-profile"),

    # 🔹 Personal Details
    path("profile/personal/", StudentPersonalDetails.as_view(), name="student-personal"),

    # 🔹 Education
    path("profile/education/", StudentEducationView.as_view(), name="student-education"),

    # 🔹 Career Preference
    path("profile/career/", StudentCareerPreferenceView.as_view(), name="student-career"),

    # Student payment/subscription canonical routes
    path("", include("Student.payment_urls")),

    # Student jobs and applications canonical routes
    path("", include("Student.job_urls")),

]