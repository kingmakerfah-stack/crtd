from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Module, SubAdminProfile
from jobs.models import Job


User = get_user_model()


class JobRBACTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="jobs-superadmin@example.com",
            password="secret123",
            role="superadmin",
        )
        self.subadmin = User.objects.create_user(
            email="jobs-subadmin@example.com",
            password="secret123",
            role="subadmin",
        )
        self.unassigned_subadmin = User.objects.create_user(
            email="jobs-unassigned@example.com",
            password="secret123",
            role="subadmin",
        )

        web_update_module = Module.objects.create(
            name="web_update",
            display_name="Web Update",
            order=1,
        )

        profile = SubAdminProfile.objects.create(user=self.subadmin, created_by=self.superadmin)
        profile.allowed_modules.set([web_update_module])
        SubAdminProfile.objects.create(user=self.unassigned_subadmin, created_by=self.superadmin)

        self.payload = {
            "job_role": "Backend Developer",
            "package": "Standard",
            "department": "Engineering",
            "total_vacancies": 2,
            "experience": "2 years",
            "location": "Remote",
            "job_mode": "Remote",
            "job_description": "Build APIs",
            "skills_required": "Python, Django",
            "eligibility": "B.Tech",
        }

    def test_jobs_list_remains_public(self):
        response = self.client.get(reverse("job-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subadmin_with_web_update_module_can_create_job(self):
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.post(reverse("job-list-create"), self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_subadmin_without_module_gets_403_on_job_create(self):
        self.client.force_authenticate(user=self.unassigned_subadmin)
        response = self.client.post(reverse("job-list-create"), self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_delete_job(self):
        job = Job.objects.create(**self.payload)
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.delete(reverse("job-detail", args=[job.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
