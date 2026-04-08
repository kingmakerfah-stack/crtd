from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Module, SubAdminProfile
from subscription.models import SubscriptionPlan


User = get_user_model()


class SubscriptionPlanRBACTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="subscription-superadmin@example.com",
            password="secret123",
            role="superadmin",
        )
        self.subadmin = User.objects.create_user(
            email="subscription-subadmin@example.com",
            password="secret123",
            role="subadmin",
        )
        self.unassigned_subadmin = User.objects.create_user(
            email="subscription-unassigned@example.com",
            password="secret123",
            role="subadmin",
        )

        membership_module = Module.objects.create(
            name="membership",
            display_name="Membership",
            order=1,
        )

        profile = SubAdminProfile.objects.create(user=self.subadmin, created_by=self.superadmin)
        profile.allowed_modules.set([membership_module])
        SubAdminProfile.objects.create(user=self.unassigned_subadmin, created_by=self.superadmin)

        self.payload = {
            "name": "Gold Plan",
            "description": "Gold membership",
            "price": str(Decimal("999.00")),
            "duration_months": 6,
            "discount": str(Decimal("10.00")),
            "currency": "INR",
            "features": "priority support",
            "is_active": True,
        }

    def test_subscription_get_remains_public(self):
        response = self.client.get(reverse("subscription-plan"))
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND))

    def test_subadmin_with_membership_module_can_update_plan(self):
        plan = SubscriptionPlan.objects.first()
        self.assertIsNotNone(plan)
        self.client.force_authenticate(user=self.subadmin)
        response = self.client.patch(
            reverse("subscription-plan"),
            {"description": "Updated by membership subadmin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subadmin_without_membership_module_gets_403_on_update(self):
        plan = SubscriptionPlan.objects.first()
        self.assertIsNotNone(plan)
        self.client.force_authenticate(user=self.unassigned_subadmin)
        response = self.client.patch(
            reverse("subscription-plan"),
            {"description": "Should be rejected"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_can_update_plan(self):
        plan = SubscriptionPlan.objects.first()
        self.assertIsNotNone(plan)
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.patch(
            reverse("subscription-plan"),
            {"description": "Updated by superadmin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
