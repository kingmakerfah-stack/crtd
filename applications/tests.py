from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from Student.models import StudentEducation, StudentPersonalDetail
from Student.models import Student
from accounts.models import (
    Module,
    SubAdminBirthStateScope,
    SubAdminCollegeStateScope,
    SubAdminModuleAccess,
    SubAdminPassingYearScope,
    SubAdminProfile,
)
from applications.models import Application, CoolDown
from jobs.models import Job


User = get_user_model()


class ApplicationRBACTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="applications-superadmin@example.com",
            password="secret123",
            role="superadmin",
        )
        self.subadmin = User.objects.create_user(
            email="applications-subadmin@example.com",
            password="secret123",
            role="subadmin",
        )
        self.unassigned_subadmin = User.objects.create_user(
            email="applications-unassigned@example.com",
            password="secret123",
            role="subadmin",
        )

        job_applications_module = Module.objects.create(
            name="job_applications",
            display_name="Job Applications",
            order=1,
        )

        profile = SubAdminProfile.objects.create(user=self.subadmin, created_by=self.superadmin)
        profile.allowed_modules.set([job_applications_module])
        SubAdminModuleAccess.objects.create(
            subadmin_profile=profile,
            module=job_applications_module,
            can_view=True,
            can_edit=True,
        )
        SubAdminBirthStateScope.objects.create(subadmin_profile=profile, state_name="Gujarat")
        SubAdminCollegeStateScope.objects.create(subadmin_profile=profile, state_name="Gujarat")
        SubAdminPassingYearScope.objects.create(subadmin_profile=profile, passing_year="2024")
        SubAdminProfile.objects.create(user=self.unassigned_subadmin, created_by=self.superadmin)

        student_user = User.objects.create_user(
            email="student-applications@example.com",
            password="secret123",
            role="student",
        )
        self.student = Student.objects.create(
            user=student_user,
            enrollment_id="ENR-RBAC-1",
            profile_completed=True,
        )
        StudentPersonalDetail.objects.create(student=self.student, birthplace_state="Gujarat")
        StudentEducation.objects.create(student=self.student, college_state="Gujarat", passing_year="2024")
        self.job = Job.objects.create(
            job_role="Backend Developer",
            package="Standard",
            department="Engineering",
            total_vacancies=2,
            experience="2 years",
            location="Remote",
            job_mode="Remote",
            job_description="Build APIs",
            skills_required="Python, Django",
            eligibility="B.Tech",
        )
        self.application = Application.objects.create(
            student=self.student,
            job=self.job,
            cooldown_days_used=10,
        )

    def test_subadmin_with_job_applications_module_can_update_cooldown_days(self):
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.put(
            reverse("cooldown-days-update"),
            {"cooldown_days": 14},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CoolDown.objects.get(id=1).cooldown_days, 14)

    def test_subadmin_without_job_applications_module_gets_403_on_cooldown_update(self):
        self.client.force_authenticate(user=self.unassigned_subadmin)
        response = self.client.put(
            reverse("cooldown-days-update"),
            {"cooldown_days": 14},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_access_job_summary(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get(reverse("admin-job-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_admin_application_detail(self):
        self.client.force_authenticate(user=self.student.user)
        response = self.client.get(reverse("admin-application-detail", args=[self.application.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_subadmin_scope_limits_application_visibility(self):
        other_user = User.objects.create_user(
            email="student-hidden@example.com",
            password="secret123",
            role="student",
        )
        other_student = Student.objects.create(
            user=other_user,
            enrollment_id="ENR-RBAC-2",
            profile_completed=True,
        )
        StudentPersonalDetail.objects.create(student=other_student, birthplace_state="Maharashtra")
        StudentEducation.objects.create(student=other_student, college_state="Karnataka", passing_year="2026")
        hidden_application = Application.objects.create(
            student=other_student,
            job=self.job,
            cooldown_days_used=5,
        )

        self.client.force_authenticate(user=self.subadmin)
        response = self.client.get(reverse("admin-job-applications", args=[self.job.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(self.application.id, returned_ids)
        self.assertNotIn(hidden_application.id, returned_ids)
