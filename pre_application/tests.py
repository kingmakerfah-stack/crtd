import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PreApplication, ReferalCode


User = get_user_model()


BASE_PRE_APPLICATION_PAYLOAD = {
    "first_name": "Asha",
    "last_name": "Patel",
    "email": "asha@example.com",
    "whatsapp_no": "+919876543210",
    "alternate_phone": "+919876543211",
    "birthplace_state": "Gujarat",
    "qualification": "B.Tech",
    "specialization": "Computer Science",
    "college_name": "Example College",
    "college_state": "Gujarat",
    "passing_year": "2024",
    "preferred_time": "Evening",
}


class PreApplicationAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="secret123",
            role="admin",
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="secret123",
            role="student",
        )

    def make_payload(self, **overrides):
        payload = BASE_PRE_APPLICATION_PAYLOAD.copy()
        payload.update(overrides)
        return payload

    def create_pre_application(self, **overrides):
        payload = self.make_payload(**overrides)
        return PreApplication.objects.create(**payload)

    def test_submit_form_returns_generated_enquiry_token_and_ignores_client_value(self):
        response = self.client.post(
            reverse("pre-application-create"),
            data=self.make_payload(enquiry_token="ENQ999999"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertRegex(response.data["enquiry_token"], r"^ENQ\d{6}$")
        self.assertNotEqual(response.data["enquiry_token"], "ENQ999999")

    def test_submit_form_generates_unique_enquiry_tokens(self):
        first_response = self.client.post(
            reverse("pre-application-create"),
            data=self.make_payload(),
            format="json",
        )
        second_response = self.client.post(
            reverse("pre-application-create"),
            data=self.make_payload(
                email="second@example.com",
                whatsapp_no="+919876543212",
                alternate_phone="+919876543213",
            ),
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(
            first_response.data["enquiry_token"],
            second_response.data["enquiry_token"],
        )

    def test_enquiry_lookup_returns_expected_basic_details_for_admin(self):
        pre_application = self.create_pre_application()
        ReferalCode.objects.create(student=pre_application, code="AB12CD34")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], pre_application.email)
        self.assertEqual(response.data["reference_code"], "AB12CD34")
        self.assertEqual(response.data["enquiry_token"], pre_application.enquiry_token)

    def test_admin_list_returns_preapplications_with_enquiry_tokens(self):
        first = self.create_pre_application()
        second = self.create_pre_application(
            email="second@example.com",
            whatsapp_no="+919876543212",
            alternate_phone="+919876543213",
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("pre-application-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        returned_tokens = {item["enquiry_token"] for item in response.data["results"]}
        self.assertEqual(returned_tokens, {first.enquiry_token, second.enquiry_token})

    def test_admin_lookup_by_email_returns_specific_preapplication(self):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("pre-application-lookup"),
            {"email": pre_application.email},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], pre_application.email)
        self.assertEqual(response.data["enquiry_token"], pre_application.enquiry_token)

    def test_admin_lookup_by_enquiry_token_returns_specific_preapplication(self):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("pre-application-lookup"),
            {"enquiry_token": pre_application.enquiry_token.lower()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["enquiry_token"], pre_application.enquiry_token)

    def test_admin_lookup_requires_exactly_one_unique_identifier(self):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.admin_user)

        both_response = self.client.get(
            reverse("pre-application-lookup"),
            {
                "email": pre_application.email,
                "enquiry_token": pre_application.enquiry_token,
            },
        )
        missing_response = self.client.get(reverse("pre-application-lookup"))

        self.assertEqual(both_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enquiry_lookup_denies_unauthenticated_and_non_admin_users(self):
        pre_application = self.create_pre_application()

        unauthenticated_response = self.client.get(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )
        self.client.force_authenticate(user=self.student_user)
        non_admin_response = self.client.get(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertIn(
            unauthenticated_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(non_admin_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_list_and_lookup_deny_non_admin_users(self):
        pre_application = self.create_pre_application()

        unauthenticated_list = self.client.get(reverse("pre-application-list"))
        unauthenticated_lookup = self.client.get(
            reverse("pre-application-lookup"),
            {"email": pre_application.email},
        )

        self.client.force_authenticate(user=self.student_user)
        non_admin_list = self.client.get(reverse("pre-application-list"))
        non_admin_lookup = self.client.get(
            reverse("pre-application-lookup"),
            {"enquiry_token": pre_application.enquiry_token},
        )

        self.assertIn(
            unauthenticated_list.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            unauthenticated_lookup.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(non_admin_list.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(non_admin_lookup.status_code, status.HTTP_403_FORBIDDEN)

    @patch("pre_application.services.EmailService.send_approval_email")
    def test_admin_can_generate_referral_by_enquiry_token(self, mock_send_email):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse(
                "create-referral-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pre_application.refresh_from_db()
        referral = ReferalCode.objects.get(student=pre_application)
        self.assertTrue(pre_application.verified)
        self.assertEqual(response.data["code"], referral.code)
        mock_send_email.assert_called_once()

    @patch("pre_application.services.EmailService.send_approval_email")
    def test_legacy_admin_referral_route_still_links_to_same_pre_application(self, mock_send_email):
        pre_application = self.create_pre_application(email="legacy@example.com")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("create-referral", args=[pre_application.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        pre_application.refresh_from_db()
        referral = ReferalCode.objects.get(student=pre_application)
        self.assertEqual(referral.student_id, pre_application.id)
        self.assertRegex(pre_application.enquiry_token, r"^ENQ\d{6}$")
        mock_send_email.assert_called_once()

    @patch("pre_application.services.EmailService.send_approval_email")
    def test_non_admin_cannot_generate_referral(self, mock_send_email):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse(
                "create-referral-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ReferalCode.objects.filter(student=pre_application).exists())
        mock_send_email.assert_not_called()

    def test_referral_validation_returns_candidate_details(self):
        pre_application = self.create_pre_application()
        pre_application.verified = True
        pre_application.save(update_fields=["verified"])
        ReferalCode.objects.create(student=pre_application, code="ZXCV1234")

        response = self.client.get(reverse("check-referral", args=["ZXCV1234"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], pre_application.email)
        self.assertEqual(response.data["reference_code"], "ZXCV1234")
        self.assertEqual(response.data["enquiry_token"], pre_application.enquiry_token)

    def test_referral_generation_route_is_post_only(self):
        pre_application = self.create_pre_application()
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse(
                "create-referral-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unknown_enquiry_lookup_returns_not_found(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            reverse("pre-application-by-enquiry-token", args=["ENQ999999"])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EnquiryTokenMigrationTests(TransactionTestCase):
    migrate_from = ("pre_application", "0001_initial")
    migrate_to = ("pre_application", "0002_enquiry_token_sequence_and_backfill")
    reset_sequences = True

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])

        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        PreApplication = old_apps.get_model("pre_application", "PreApplication")
        PreApplication.objects.create(**BASE_PRE_APPLICATION_PAYLOAD)
        PreApplication.objects.create(
            **{
                **BASE_PRE_APPLICATION_PAYLOAD,
                "email": "migrated@example.com",
                "whatsapp_no": "+919876543214",
                "alternate_phone": "+919876543215",
            }
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])

    def test_migration_backfills_unique_enquiry_tokens(self):
        apps = self.executor.loader.project_state([self.migrate_to]).apps
        PreApplication = apps.get_model("pre_application", "PreApplication")
        EnquiryTokenSequence = apps.get_model("pre_application", "EnquiryTokenSequence")

        tokens = list(
            PreApplication.objects.order_by("pk").values_list("enquiry_token", flat=True)
        )
        self.assertEqual(len(tokens), 2)
        self.assertEqual(len(tokens), len(set(tokens)))
        self.assertTrue(all(re.match(r"^ENQ\d{6}$", token) for token in tokens))

        sequence = EnquiryTokenSequence.objects.get(pk=1)
        self.assertEqual(sequence.next_value, 3)
