from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from Student.models import Student
from applications.models import Application
from jobs.models import Job
from payments.models import StudentPayment, StudentSubscription


User = get_user_model()


class StudentGatedEndpointTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="student-endpoints@example.com",
			password="secret123",
			role="student",
		)
		self.student = Student.objects.create(
			user=self.user,
			enrollment_id="ENR-STU-1",
			profile_completed=True,
		)
		self.job = Job.objects.create(
			job_role="Backend Developer",
			package="Standard",
			department="Engineering",
			total_vacancies=2,
			experience="2 years",
			location="Remote",
			job_mode="Remote",
			job_description="Build APIs",
			skills_required="Python, Django",
			eligibility="B.Tech",
		)

	def test_student_jobs_list_visible_without_payment(self):
		self.client.force_authenticate(user=self.user)
		response = self.client.get(reverse("student-jobs"))
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertFalse(response.data["subscription"]["is_paid"])
		self.assertEqual(len(response.data["jobs"]), 1)

	def test_student_applications_requires_active_subscription(self):
		self.client.force_authenticate(user=self.user)
		response = self.client.get(reverse("student-applications"))
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_student_applications_with_active_subscription_returns_own_data(self):
		payment = StudentPayment.objects.create(
			student=self.user,
			razorpay_order_id="order_student_tests",
			amount=1000,
			status=StudentPayment.STATUS_SUCCESS,
		)
		StudentSubscription.objects.create(
			student=self.user,
			student_payment=payment,
			status=StudentSubscription.STATUS_ACTIVE,
			payment_date=date.today(),
			expiry_date=date.today() + timedelta(days=10),
			registration_number="CRTD2099000001",
		)
		Application.objects.create(student=self.student, job=self.job, cooldown_days_used=0)

		self.client.force_authenticate(user=self.user)
		response = self.client.get(reverse("student-applications"))
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
