from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser, EmailOTP
from utils.email_service import EmailService


class OTPVerificationTests(TestCase):
	def setUp(self):
		self.user = CustomUser.objects.create_user(
			email='otp-user@example.com',
			password='TestPass@123',
			role='student',
		)

	def test_verify_otp_succeeds_for_hashed_otp(self):
		EmailOTP.objects.create(
			user=self.user,
			purpose='email_verification',
			otp=make_password('1234'),
			expires_at=timezone.now() + timedelta(minutes=10),
			is_verified=False,
		)

		result = EmailService.verify_otp(self.user, '1234', purpose='email_verification')

		self.assertTrue(result['success'])
		self.user.refresh_from_db()
		self.assertTrue(self.user.email_verified)

	def test_verify_otp_supports_legacy_plaintext_otp(self):
		EmailOTP.objects.create(
			user=self.user,
			purpose='login_otp',
			otp='9876',
			expires_at=timezone.now() + timedelta(minutes=10),
			is_verified=False,
		)

		result = EmailService.verify_otp(self.user, '9876', purpose='login_otp')

		self.assertTrue(result['success'])

	def test_verify_otp_fails_on_wrong_code(self):
		EmailOTP.objects.create(
			user=self.user,
			purpose='password_reset',
			otp=make_password('5555'),
			expires_at=timezone.now() + timedelta(minutes=10),
			is_verified=False,
		)

		result = EmailService.verify_otp(self.user, '0000', purpose='password_reset')

		self.assertFalse(result['success'])
		self.assertEqual(result['message'], 'Invalid OTP. Please try again.')


class AuthResponseNormalizationTests(APITestCase):
	def setUp(self):
		self.user = CustomUser.objects.create_user(
			email='auth-user@example.com',
			password='SecurePass@123',
			role='student',
			email_verified=False,
		)

	def test_login_unverified_user_returns_generic_403(self):
		response = self.client.post(
			reverse('token_obtain_pair'),
			{'email': self.user.email, 'password': 'SecurePass@123'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(response.data['error'], 'Invalid credentials or account state.')

	def test_otp_request_unknown_email_returns_generic_success(self):
		response = self.client.post(
			reverse('otp_request'),
			{'email': 'missing@example.com', 'purpose': 'password_reset'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			response.data['message'],
			'If an account exists for this email, an OTP has been sent.',
		)

	def test_otp_verify_unknown_email_returns_generic_failure(self):
		response = self.client.post(
			reverse('otp_verify'),
			{'email': 'missing@example.com', 'otp': '1234', 'purpose': 'password_reset'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['error'], 'Invalid or expired OTP.')

	def test_password_reset_unknown_email_returns_generic_failure(self):
		response = self.client.post(
			reverse('password_reset'),
			{'email': 'missing@example.com', 'new_password': 'NewSecurePass@123'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data['error'], 'Password reset request is invalid.')
