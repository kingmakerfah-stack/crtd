from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser, EmailOTP, Module, SubAdminProfile
from accounts.utils import clear_user_invalidation, get_tokens_for_user, invalidate_user_session
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
		self.assertEqual(response.data['error'], 'Email not verified.')

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


class RBACAdminPortalTests(APITestCase):
	def setUp(self):
		self.superadmin = CustomUser.objects.create_user(
			email='superadmin@example.com',
			password='SuperPass@123',
			role='superadmin',
			name='Root Admin',
		)
		self.subadmin = CustomUser.objects.create_user(
			email='subadmin@example.com',
			password='SubPass@123',
			role='subadmin',
			name='Sub Admin',
		)
		self.module_dashboard = Module.objects.create(
			name='dashboard',
			display_name='Dashboard',
			order=1,
		)
		self.module_analytics = Module.objects.create(
			name='analytics',
			display_name='Analytics',
			order=2,
		)
		self.module_subadmin = Module.objects.create(
			name='sub_admin',
			display_name='Sub Admin',
			order=3,
		)
		SubAdminProfile.objects.create(user=self.subadmin, created_by=self.superadmin)

	def test_superadmin_can_list_modules(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.get(reverse('rbac-module-list'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		returned = {item['name'] for item in response.data}
		self.assertEqual(returned, {'dashboard', 'analytics', 'sub_admin'})

	def test_superadmin_can_update_subadmin_module_access(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.patch(
			reverse('rbac-subadmin-update-access', args=[self.subadmin.id]),
			{'modules': ['dashboard']},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.subadmin.refresh_from_db()
		self.assertEqual(self.subadmin.subadmin_profile.get_module_names(), ['dashboard'])

	def test_non_superadmin_cannot_manage_modules(self):
		self.client.force_authenticate(self.subadmin)
		response = self.client.get(reverse('rbac-module-list'))
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_subadmin_with_superuser_flag_still_cannot_manage_modules(self):
		self.subadmin.is_superuser = True
		self.subadmin.save(update_fields=['is_superuser'])

		self.client.force_authenticate(self.subadmin)
		response = self.client.get(reverse('rbac-module-list'))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_rbac_admin_verify_marks_email_verified_for_login_otp(self):
		EmailOTP.objects.create(
			user=self.subadmin,
			purpose='login_otp',
			otp=make_password('123456'),
			expires_at=timezone.now() + timedelta(minutes=10),
			is_verified=False,
		)

		response = self.client.post(
			reverse('rbac-admin-otp-verify'),
			{'email': self.subadmin.email, 'otp': '123456'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.subadmin.refresh_from_db()
		self.assertTrue(self.subadmin.email_verified)

	def test_invalidated_session_returns_401_on_me(self):
		tokens = get_tokens_for_user(self.subadmin)
		invalidate_user_session(self.subadmin.pk)

		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
		response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_raw_authorization_token_header_allows_me_access(self):
		clear_user_invalidation(self.subadmin.pk)
		tokens = get_tokens_for_user(self.subadmin)

		self.client.credentials(HTTP_AUTHORIZATION=tokens['access'])
		response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['role'], 'subadmin')

	def test_malformed_three_part_authorization_header_is_rejected(self):
		tokens = get_tokens_for_user(self.subadmin)

		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']} extra")
		response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_superadmin_can_update_subadmin_role_and_old_session_is_invalidated(self):
		tokens = get_tokens_for_user(self.subadmin)

		self.client.force_authenticate(self.superadmin)
		update_response = self.client.patch(
			reverse('rbac-subadmin-update-role', args=[self.subadmin.id]),
			{'role': 'sales'},
			format='json',
		)

		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.subadmin.refresh_from_db()
		self.assertEqual(self.subadmin.role, 'sales')

		self.client.force_authenticate(user=None)
		self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
		me_response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_role_update_endpoint_rejects_superadmin_role_assignment(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.patch(
			reverse('rbac-subadmin-update-role', args=[self.subadmin.id]),
			{'role': 'superadmin'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_superadmin_cannot_demote_self_via_role_endpoint(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.patch(
			reverse('rbac-subadmin-update-role', args=[self.superadmin.id]),
			{'role': 'sales'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_subadmin_cannot_create_or_list_subadmins(self):
		self.client.force_authenticate(self.subadmin)

		list_response = self.client.get(reverse('rbac-subadmin-list'))
		create_response = self.client.post(
			reverse('rbac-subadmin-create'),
			{
				'email': 'new-sub@example.com',
				'name': 'New Sub',
				'password': 'NewSubPass@123',
				'modules': ['dashboard'],
			},
			format='json',
		)

		self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_subadmin_with_sub_admin_module_can_manage_subadmins(self):
		self.subadmin.subadmin_profile.allowed_modules.add(self.module_subadmin)
		self.client.force_authenticate(self.subadmin)

		list_response = self.client.get(reverse('rbac-subadmin-list'))
		create_response = self.client.post(
			reverse('rbac-subadmin-create'),
			{
				'email': 'managed-sub@example.com',
				'name': 'Managed Sub',
				'password': 'ManagedSubPass@123',
				'modules': ['dashboard'],
			},
			format='json',
		)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		new_user_id = create_response.data['user_id']
		update_response = self.client.patch(
			reverse('rbac-subadmin-update-access', args=[new_user_id]),
			{'modules': ['analytics']},
			format='json',
		)
		delete_response = self.client.delete(reverse('rbac-subadmin-delete', args=[new_user_id]))

		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

	def test_me_ignores_superuser_flag_for_subadmin_capabilities(self):
		self.subadmin.is_superuser = True
		self.subadmin.save(update_fields=['is_superuser'])

		self.client.force_authenticate(self.subadmin)
		response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['role'], 'subadmin')
		self.assertFalse(response.data['can_manage_subadmins'])
		self.assertEqual(response.data['allowed_modules'], [])
