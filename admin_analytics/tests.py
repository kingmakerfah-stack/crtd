from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from pre_application.models import PreApplication

from .models import EnquiryAnalytics


User = get_user_model()


class EnquiryAnalyticsTests(APITestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email="analytics-admin@example.com",
			password="secret123",
			role="admin",
		)

	def create_pre_application(self, **overrides):
		payload = {
			"first_name": "Asha",
			"last_name": "Patel",
			"email": "analytics-preapp@example.com",
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
		payload.update(overrides)
		return PreApplication.objects.create(**payload)

	def test_enquiry_analytics_token_uses_preapplication_token(self):
		pre_application = self.create_pre_application()

		analytics = EnquiryAnalytics.objects.create(
			student=pre_application,
			enquiry_token="ENQ999999",
		)

		self.assertEqual(analytics.enquiry_token, pre_application.enquiry_token)

	def test_enquiry_table_uses_preapplication_token(self):
		pre_application = self.create_pre_application(email="table-token@example.com")
		self.client.force_authenticate(user=self.admin_user)

		response = self.client.get("/api/admin-analytics/enquiry-table/")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data[0]["enquiry_token"], pre_application.enquiry_token)
