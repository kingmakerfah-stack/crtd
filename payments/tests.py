import json
from datetime import date, timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from Student.models import Student
from payments.models import StudentPayment, StudentSubscription


User = get_user_model()


@override_settings(
	SUBSCRIPTION_AMOUNT_PAISE=200000,
	SUBSCRIPTION_DURATION_MONTHS=6,
	RAZORPAY_KEY_ID="test_key",
	RAZORPAY_WEBHOOK_SECRET="whsec_test",
)
class StudentPaymentFlowTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="student-payments@example.com",
			password="secret123",
			role="student",
		)
		Student.objects.create(user=self.user, enrollment_id="ENR-PAY-1", profile_completed=True)

	@patch("payments.views.create_razorpay_order")
	def test_create_order_creates_student_payment_row(self, mock_create_order):
		mock_create_order.return_value = {"id": "order_123"}

		self.client.force_authenticate(user=self.user)
		response = self.client.post(reverse("create_order"), {}, format="json")

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["order_id"], "order_123")
		self.assertTrue(StudentPayment.objects.filter(razorpay_order_id="order_123").exists())

	@patch("payments.views.get_razorpay_client")
	def test_webhook_success_is_idempotent(self, mock_client_factory):
		payment = StudentPayment.objects.create(
			student=self.user,
			razorpay_order_id="order_abc",
			amount=200000,
			status=StudentPayment.STATUS_CREATED,
		)

		client = Mock()
		client.utility.verify_webhook_signature.return_value = None
		mock_client_factory.return_value = client

		payload = {
			"event": "payment.captured",
			"payload": {
				"payment": {
					"entity": {
						"order_id": "order_abc",
						"id": "pay_abc",
					}
				}
			},
		}

		first = self.client.post(
			reverse("razorpay_webhook"),
			data=json.dumps(payload),
			content_type="application/json",
			HTTP_X_RAZORPAY_SIGNATURE="sig",
		)
		self.assertEqual(first.status_code, status.HTTP_200_OK)

		payment.refresh_from_db()
		self.assertEqual(payment.status, StudentPayment.STATUS_SUCCESS)

		subscription = StudentSubscription.objects.get(student=self.user)
		self.assertEqual(subscription.status, StudentSubscription.STATUS_ACTIVE)
		self.assertEqual(subscription.student_payment_id, payment.id)
		first_registration = subscription.registration_number
		self.assertIsNotNone(first_registration)

		second = self.client.post(
			reverse("razorpay_webhook"),
			data=json.dumps(payload),
			content_type="application/json",
			HTTP_X_RAZORPAY_SIGNATURE="sig",
		)
		self.assertEqual(second.status_code, status.HTTP_200_OK)

		subscription.refresh_from_db()
		self.assertEqual(subscription.registration_number, first_registration)

	@patch("payments.views.get_razorpay_client")
	def test_webhook_invalid_signature_does_not_mutate_payment(self, mock_client_factory):
		payment = StudentPayment.objects.create(
			student=self.user,
			razorpay_order_id="order_bad_sig",
			amount=200000,
			status=StudentPayment.STATUS_CREATED,
		)

		client = Mock()
		client.utility.verify_webhook_signature.side_effect = Exception("bad signature")
		mock_client_factory.return_value = client

		payload = {
			"event": "payment.captured",
			"payload": {"payment": {"entity": {"order_id": "order_bad_sig", "id": "pay_bad"}}},
		}

		response = self.client.post(
			reverse("razorpay_webhook"),
			data=json.dumps(payload),
			content_type="application/json",
			HTTP_X_RAZORPAY_SIGNATURE="bad",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		payment.refresh_from_db()
		self.assertEqual(payment.status, StudentPayment.STATUS_CREATED)
		self.assertFalse(StudentSubscription.objects.filter(student=self.user).exists())

	def test_payment_failed_is_user_scoped(self):
		other = User.objects.create_user(
			email="other-student@example.com",
			password="secret123",
			role="student",
		)
		Student.objects.create(user=other, enrollment_id="ENR-PAY-2", profile_completed=True)

		StudentPayment.objects.create(
			student=other,
			razorpay_order_id="order_other",
			amount=1000,
			status=StudentPayment.STATUS_CREATED,
		)

		self.client.force_authenticate(user=self.user)
		response = self.client.post(
			reverse("payment_failed"),
			{"razorpay_order_id": "order_other", "razorpay_payment_id": "pay_x"},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
