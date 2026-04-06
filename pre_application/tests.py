import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Module, SubAdminProfile
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
            role="subadmin",
        )
        self.superadmin_user = User.objects.create_user(
            email="superadmin@example.com",
            password="secret123",
            role="superadmin",
        )
        self.subadmin_user = User.objects.create_user(
            email="subadmin@example.com",
            password="secret123",
            role="subadmin",
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="secret123",
            role="student",
        )

        self.module_enquiry = Module.objects.create(
            name="enquiry_form",
            display_name="Enquiry Form",
            order=1,
        )
        self.module_reference_code = Module.objects.create(
            name="reference_code",
            display_name="Reference Code",
            order=2,
        )
        self.module_job_apps = Module.objects.create(
            name="job_applications",
            display_name="Job Applications",
            order=3,
        )

        admin_profile = SubAdminProfile.objects.create(
            user=self.admin_user,
            created_by=self.superadmin_user,
        )
        admin_profile.allowed_modules.set([self.module_enquiry, self.module_reference_code])

        subadmin_profile = SubAdminProfile.objects.create(
            user=self.subadmin_user,
            created_by=self.superadmin_user,
        )
        subadmin_profile.allowed_modules.set([self.module_job_apps])

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

    def test_submit_form_succeeds_even_with_invalid_authorization_header(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = self.client.post(
            reverse("pre-application-create"),
            data=self.make_payload(email="invalid-header@example.com"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertRegex(response.data["enquiry_token"], r"^ENQ\d{6}$")

    def test_submit_form_defaults_status_to_pending(self):
        response = self.client.post(
            reverse("pre-application-create"),
            data=self.make_payload(email="status-default@example.com", status="completed"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

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
        first_item = response.data["results"][0]
        self.assertIn("birthplace_state", first_item)
        self.assertIn("qualification", first_item)
        self.assertIn("specialization", first_item)
        self.assertIn("college_name", first_item)
        self.assertIn("college_state", first_item)
        self.assertIn("passing_year", first_item)
        self.assertIn("preferred_time", first_item)
        self.assertIn("status", first_item)

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

    def test_referral_validation_ignores_invalid_authorization_header(self):
        pre_application = self.create_pre_application(email="referral-header@example.com")
        pre_application.verified = True
        pre_application.save(update_fields=["verified"])
        ReferalCode.objects.create(student=pre_application, code="QWER1234")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        response = self.client.get(reverse("check-referral", args=["QWER1234"]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reference_code"], "QWER1234")

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

    def test_admin_and_superadmin_can_update_preapplication_status(self):
        pre_application = self.create_pre_application(email="status-update@example.com")

        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.patch(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            ),
            data={"status": "completed"},
            format="json",
        )
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data["status"], "completed")

        self.client.force_authenticate(user=self.superadmin_user)
        superadmin_response = self.client.patch(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            ),
            data={"status": "not interested"},
            format="json",
        )
        self.assertEqual(superadmin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(superadmin_response.data["status"], "not interested")

        pre_application.refresh_from_db()
        self.assertEqual(pre_application.status, "not interested")

    def test_subadmin_cannot_update_preapplication_status(self):
        pre_application = self.create_pre_application(email="subadmin-status@example.com")
        self.client.force_authenticate(user=self.subadmin_user)

        response = self.client.patch(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            ),
            data={"status": "completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        pre_application.refresh_from_db()
        self.assertEqual(pre_application.status, "pending")

    def test_subadmin_without_enquiry_module_cannot_archive_preapplication(self):
        pre_application = self.create_pre_application(email="archive-subadmin@example.com")
        self.client.force_authenticate(user=self.subadmin_user)

        response = self.client.patch(
            reverse(
                "archive-pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            ),
            data={"deleted_reason": "Candidate asked to stop follow-up"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        pre_application.refresh_from_db()
        self.assertFalse(pre_application.is_deleted)
        self.assertIsNone(pre_application.deleted_at)
        self.assertIsNone(pre_application.deleted_by_id)
        self.assertIsNone(pre_application.deleted_reason)
        self.assertTrue(PreApplication.objects.filter(pk=pre_application.pk).exists())

    def test_archived_rows_hidden_from_custom_admin_list_and_lookup_by_default(self):
        active = self.create_pre_application(email="active@example.com")
        archived = self.create_pre_application(email="archived-hidden@example.com")
        archived.is_deleted = True
        archived.save(update_fields=["is_deleted"])
        self.client.force_authenticate(user=self.admin_user)

        list_response = self.client.get(reverse("pre-application-list"))
        lookup_response = self.client.get(
            reverse("pre-application-lookup"),
            {"email": archived.email},
        )
        token_response = self.client.get(
            reverse("pre-application-by-enquiry-token", args=[archived.enquiry_token])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        tokens = {item["enquiry_token"] for item in list_response.data["results"]}
        self.assertIn(active.enquiry_token, tokens)
        self.assertNotIn(archived.enquiry_token, tokens)
        self.assertEqual(lookup_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(token_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_include_deleted_true_only_works_for_superadmin(self):
        archived = self.create_pre_application(email="include-deleted@example.com")
        archived.is_deleted = True
        archived.save(update_fields=["is_deleted"])

        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.get(
            reverse("pre-application-list"),
            {"include_deleted": "true"},
        )

        self.client.force_authenticate(user=self.superadmin_user)
        superadmin_list_response = self.client.get(
            reverse("pre-application-list"),
            {"include_deleted": "true"},
        )
        superadmin_lookup_response = self.client.get(
            reverse("pre-application-lookup"),
            {"email": archived.email, "include_deleted": "true"},
        )

        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            archived.enquiry_token,
            {item["enquiry_token"] for item in admin_response.data["results"]},
        )

        self.assertEqual(superadmin_list_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            archived.enquiry_token,
            {item["enquiry_token"] for item in superadmin_list_response.data["results"]},
        )
        self.assertEqual(superadmin_lookup_response.status_code, status.HTTP_200_OK)
        self.assertEqual(superadmin_lookup_response.data["enquiry_token"], archived.enquiry_token)

    @patch("pre_application.services.EmailService.send_approval_email")
    def test_archived_preapplication_blocks_referral_generation(self, mock_send_email):
        pre_application = self.create_pre_application(email="archived-referral@example.com")
        pre_application.is_deleted = True
        pre_application.save(update_fields=["is_deleted"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse(
                "create-referral-by-enquiry-token",
                args=[pre_application.enquiry_token],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ReferalCode.objects.filter(student=pre_application).exists())
        mock_send_email.assert_not_called()

    def test_archived_preapplication_blocks_status_update(self):
        pre_application = self.create_pre_application(email="archived-status@example.com")
        pre_application.is_deleted = True
        pre_application.save(update_fields=["is_deleted"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            reverse(
                "pre-application-by-enquiry-token",
                args=[pre_application.enquiry_token],
            ),
            data={"status": "completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        pre_application.refresh_from_db()
        self.assertEqual(pre_application.status, "pending")

    def test_restore_flow_clears_archive_metadata_for_admin_and_superadmin(self):
        pre_application = self.create_pre_application(email="restore-flow@example.com")
        pre_application.is_deleted = True
        pre_application.deleted_reason = "No longer interested"
        pre_application.deleted_by = self.admin_user
        pre_application.save(update_fields=["is_deleted", "deleted_reason", "deleted_by"])

        self.client.force_authenticate(user=self.admin_user)
        admin_restore = self.client.patch(
            reverse("restore-pre-application-by-enquiry-token", args=[pre_application.enquiry_token]),
            format="json",
        )

        self.assertEqual(admin_restore.status_code, status.HTTP_200_OK)
        pre_application.refresh_from_db()
        self.assertFalse(pre_application.is_deleted)
        self.assertIsNone(pre_application.deleted_reason)
        self.assertIsNone(pre_application.deleted_by)

        self.client.force_authenticate(user=self.subadmin_user)
        subadmin_restore = self.client.patch(
            reverse("restore-pre-application-by-enquiry-token", args=[pre_application.enquiry_token]),
            format="json",
        )
        self.assertEqual(subadmin_restore.status_code, status.HTTP_403_FORBIDDEN)

        pre_application.is_deleted = True
        pre_application.save(update_fields=["is_deleted"])
        self.client.force_authenticate(user=self.superadmin_user)
        superadmin_restore = self.client.patch(
            reverse("restore-pre-application-by-enquiry-token", args=[pre_application.enquiry_token]),
            format="json",
        )
        self.assertEqual(superadmin_restore.status_code, status.HTTP_200_OK)


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
