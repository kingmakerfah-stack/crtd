from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CustomUser, EmailOTP, Module, SubAdminModuleAccess, SubAdminProfile
from accounts.utils import clear_user_invalidation, get_tokens_for_user, invalidate_user_session, is_user_invalidated
from pre_application.models import PreApplication, ReferalCode
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


class ChangePasswordTests(APITestCase):
	def setUp(self):
		self.student = CustomUser.objects.create_user(
			email='student-change@example.com',
			password='OldPass@123',
			role='student',
		)
		self.subadmin = CustomUser.objects.create_user(
			email='subadmin-change@example.com',
			password='SubOldPass@123',
			role='subadmin',
		)

	def test_student_can_change_password_and_session_is_invalidated(self):
		self.client.force_authenticate(self.student)
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'OldPass@123',
				'new_password': 'NewPass@123',
				'confirm_new_password': 'NewPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.student.refresh_from_db()
		self.assertTrue(self.student.check_password('NewPass@123'))
		self.assertTrue(is_user_invalidated(self.student.pk))

	def test_change_password_rejects_wrong_current_password(self):
		self.client.force_authenticate(self.student)
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'WrongPass@123',
				'new_password': 'NewPass@123',
				'confirm_new_password': 'NewPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_change_password_rejects_mismatched_new_passwords(self):
		self.client.force_authenticate(self.student)
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'OldPass@123',
				'new_password': 'NewPass@123',
				'confirm_new_password': 'AnotherNewPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_change_password_rejects_same_as_current_password(self):
		self.client.force_authenticate(self.student)
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'OldPass@123',
				'new_password': 'OldPass@123',
				'confirm_new_password': 'OldPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_change_password_requires_authentication(self):
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'OldPass@123',
				'new_password': 'NewPass@123',
				'confirm_new_password': 'NewPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_change_password_forbidden_for_non_student(self):
		self.client.force_authenticate(self.subadmin)
		response = self.client.post(
			reverse('change_password'),
			{
				'current_password': 'SubOldPass@123',
				'new_password': 'SubNewPass@123',
				'confirm_new_password': 'SubNewPass@123',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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
		returned = {item['name'] for item in response.data['results']}
		self.assertEqual(returned, {'dashboard', 'analytics', 'sub_admin'})

	def test_superadmin_can_update_subadmin_module_access(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.patch(
			reverse('rbac-subadmin-update-access', args=[self.subadmin.id]),
			{'module_accesses': [{'module': 'dashboard', 'can_view': True, 'can_edit': False}]},
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
		with self.captureOnCommitCallbacks(execute=True):
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

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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
		SubAdminModuleAccess.objects.create(
			subadmin_profile=self.subadmin.subadmin_profile,
			module=self.module_subadmin,
			can_view=True,
			can_edit=True,
		)
		self.client.force_authenticate(self.subadmin)

		list_response = self.client.get(reverse('rbac-subadmin-list'))
		create_response = self.client.post(
			reverse('rbac-subadmin-create'),
			{
				'email': 'managed-sub@example.com',
				'name': 'Managed Sub',
				'password': 'ManagedSubPass@123',
				'confirm_password': 'ManagedSubPass@123',
				'is_active': True,
				'module_accesses': [{'module': 'dashboard', 'can_view': True, 'can_edit': False}],
				'birth_states': ['Maharashtra'],
				'college_states': ['Maharashtra'],
				'passing_years': ['2026'],
			},
			format='json',
		)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		new_user_id = create_response.data['user_id']
		update_response = self.client.patch(
			reverse('rbac-subadmin-update-access', args=[new_user_id]),
			{'module_accesses': [{'module': 'analytics', 'can_view': True, 'can_edit': False}]},
			format='json',
		)
		delete_response = self.client.delete(reverse('rbac-subadmin-delete', args=[new_user_id]))

		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(delete_response.status_code, status.HTTP_200_OK)

	def test_subadmin_with_module_only_lists_owned_subadmins(self):
		SubAdminModuleAccess.objects.create(
			subadmin_profile=self.subadmin.subadmin_profile,
			module=self.module_subadmin,
			can_view=True,
			can_edit=True,
		)
		owned = CustomUser.objects.create_user(
			email='owned-sub@example.com',
			password='OwnedPass@123',
			role='subadmin',
			name='Owned Sub',
		)
		other_owner = CustomUser.objects.create_user(
			email='other-owner@example.com',
			password='OwnerPass@123',
			role='superadmin',
			name='Other Owner',
		)
		SubAdminProfile.objects.create(user=owned, created_by=self.subadmin)
		external = CustomUser.objects.create_user(
			email='external-sub@example.com',
			password='ExternalPass@123',
			role='subadmin',
			name='External Sub',
		)
		SubAdminProfile.objects.create(user=external, created_by=other_owner)

		self.client.force_authenticate(self.subadmin)
		response = self.client.get(reverse('rbac-subadmin-list'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		emails = {item['email'] for item in response.data['results']}
		self.assertIn(owned.email, emails)
		self.assertNotIn(external.email, emails)

	def test_cache_failure_does_not_mark_user_invalidated(self):
		with patch('accounts.utils.cache.get', side_effect=RuntimeError('cache down')):
			self.assertFalse(is_user_invalidated(self.subadmin.pk))

	def test_subadmin_cannot_update_access_for_unmanaged_subadmin(self):
		SubAdminModuleAccess.objects.create(
			subadmin_profile=self.subadmin.subadmin_profile,
			module=self.module_subadmin,
			can_view=True,
			can_edit=True,
		)
		other_superadmin = CustomUser.objects.create_user(
			email='other-superadmin@example.com',
			password='OtherSuperPass@123',
			role='superadmin',
			name='Other Super',
		)
		external_subadmin = CustomUser.objects.create_user(
			email='external-manage@example.com',
			password='ExternalManagePass@123',
			role='subadmin',
			name='External Manage',
		)
		SubAdminProfile.objects.create(user=external_subadmin, created_by=other_superadmin)

		self.client.force_authenticate(self.subadmin)
		response = self.client.patch(
			reverse('rbac-subadmin-update-access', args=[external_subadmin.id]),
			{'module_accesses': [{'module': 'dashboard', 'can_view': True, 'can_edit': False}]},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_create_subadmin_requires_confirm_password_and_persists_scope(self):
		self.client.force_authenticate(self.superadmin)
		response = self.client.post(
			reverse('rbac-subadmin-create'),
			{
				'email': 'scoped-subadmin@example.com',
				'name': 'Scoped Subadmin',
				'password': 'ScopedPass@123',
				'confirm_password': 'ScopedPass@123',
				'is_active': False,
				'account_access_start': '2026-01-01T00:00:00Z',
				'account_access_end': '2026-12-31T23:59:59Z',
				'module_accesses': [
					{
						'module': 'dashboard',
						'can_view': True,
						'can_edit': False,
					}
				],
				'birth_states': ['Maharashtra'],
				'college_states': ['Karnataka'],
				'passing_years': ['2026'],
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		created_user = CustomUser.objects.get(email='scoped-subadmin@example.com')
		self.assertFalse(created_user.is_active)
		self.assertEqual(created_user.subadmin_profile.birth_state_scopes.count(), 1)
		self.assertEqual(created_user.subadmin_profile.module_accesses.count(), 1)

	def test_subadmin_without_edit_toggle_cannot_manage_subadmins(self):
		SubAdminModuleAccess.objects.create(
			subadmin_profile=self.subadmin.subadmin_profile,
			module=self.module_subadmin,
			can_view=True,
			can_edit=False,
		)

		self.client.force_authenticate(self.subadmin)
		response = self.client.get(reverse('rbac-module-list'))
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RegistrationFlowTests(APITestCase):
	def setUp(self):
		self.pre_application = PreApplication.objects.create(
			first_name='Asha',
			last_name='Patel',
			email='asha-register@example.com',
			whatsapp_no='+919876543210',
			alternate_phone='+919876543211',
			birthplace_state='Gujarat',
			qualification='B.Tech',
			specialization='CSE',
			college_name='Example College',
			college_state='Gujarat',
			passing_year='2024',
			preferred_time='Evening',
			verified=True,
		)
		self.referral = ReferalCode.objects.create(
			student=self.pre_application,
			code='REG12345',
			status=ReferalCode.STATUS_NOT_USED,
			is_used=False,
		)

	@patch('utils.email_service.EmailService.send_verification_otp')
	def test_register_consumes_referral_once(self, mock_send_otp):
		with self.captureOnCommitCallbacks(execute=True):
			first_response = self.client.post(
				reverse('register'),
				{
					'email': self.pre_application.email,
					'password': 'SecurePass@123',
					'confirm_password': 'SecurePass@123',
					'reference_code': self.referral.code,
				},
				format='json',
			)
		second_response = self.client.post(
			reverse('register'),
			{
				'email': self.pre_application.email,
				'password': 'SecurePass@123',
				'confirm_password': 'SecurePass@123',
				'reference_code': self.referral.code,
			},
			format='json',
		)

		self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.referral.refresh_from_db()
		self.assertEqual(self.referral.status, ReferalCode.STATUS_ACCOUNT_CREATED)
		self.assertTrue(self.referral.is_used)
		self.assertEqual(mock_send_otp.call_count, 1)

	def test_me_ignores_superuser_flag_for_subadmin_capabilities(self):
		creator = CustomUser.objects.create_user(
			email='creator@example.com',
			password='CreatorPass@123',
			role='superadmin',
			name='Creator',
		)
		subadmin = CustomUser.objects.create_user(
			email='flagged-subadmin@example.com',
			password='FlaggedPass@123',
			role='subadmin',
			name='Flagged Subadmin',
		)
		SubAdminProfile.objects.create(user=subadmin, created_by=creator)
		subadmin.is_superuser = True
		subadmin.save(update_fields=['is_superuser'])

		self.client.force_authenticate(subadmin)
		response = self.client.get(reverse('rbac-admin-me'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['role'], 'subadmin')
		self.assertFalse(response.data['can_manage_subadmins'])
		self.assertEqual(response.data['allowed_modules'], [])
