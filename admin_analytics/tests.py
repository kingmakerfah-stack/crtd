from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import (
    Module,
    SubAdminBirthStateScope,
    SubAdminCollegeStateScope,
    SubAdminPassingYearScope,
    SubAdminProfile,
)
from pre_application.models import PreApplication


User = get_user_model()


class AdminAnalyticsRBACTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="analytics-superadmin@example.com",
            password="secret123",
            role="superadmin",
        )
        self.subadmin = User.objects.create_user(
            email="analytics-subadmin@example.com",
            password="secret123",
            role="subadmin",
        )
        self.unassigned_subadmin = User.objects.create_user(
            email="analytics-unassigned@example.com",
            password="secret123",
            role="subadmin",
        )

        self.enquiry_module = Module.objects.create(
            name="enquiry_form",
            display_name="Enquiry Form",
            order=1,
        )
        self.payment_module = Module.objects.create(
            name="payment",
            display_name="Payment",
            order=2,
        )
        self.web_update_module = Module.objects.create(
            name="web_update",
            display_name="Web Update",
            order=3,
        )

        profile = SubAdminProfile.objects.create(user=self.subadmin, created_by=self.superadmin)
        profile.allowed_modules.set([self.enquiry_module, self.payment_module, self.web_update_module])
        SubAdminBirthStateScope.objects.create(subadmin_profile=profile, state_name="Gujarat")
        SubAdminCollegeStateScope.objects.create(subadmin_profile=profile, state_name="Gujarat")
        SubAdminPassingYearScope.objects.create(subadmin_profile=profile, passing_year="2024")
        SubAdminProfile.objects.create(user=self.unassigned_subadmin, created_by=self.superadmin)

        PreApplication.objects.create(
            first_name="Asha",
            last_name="Patel",
            email="analytics-preapp@example.com",
            whatsapp_no="+919876543210",
            alternate_phone="+919876543211",
            birthplace_state="Gujarat",
            qualification="B.Tech",
            specialization="CSE",
            college_name="Example College",
            college_state="Gujarat",
            passing_year="2024",
            preferred_time="Evening",
        )

    def test_subadmin_with_enquiry_module_can_access_enquiry_table(self):
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.get("/api/admin-analytics/enquiry-table/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subadmin_without_module_gets_403_on_enquiry_table(self):
        self.client.force_authenticate(user=self.unassigned_subadmin)
        response = self.client.get("/api/admin-analytics/enquiry-table/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_access_payment_analytics(self):
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get("/api/admin-analytics/payments-analytics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subadmin_without_web_update_module_gets_403_on_testimonials(self):
        self.client.force_authenticate(user=self.unassigned_subadmin)
        response = self.client.get("/api/admin-analytics/testimonials/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
