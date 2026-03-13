from django.db import models

# Create your models here.
import random

from django.db import models
from pre_application.models import PreApplication


class EnquiryAnalytics(models.Model):

    STATUS_CHOICES = (
        ("received", "Received"),
        ("done", "Enquiry Done"),
        ("pending", "Pending"),
        ("not_interested", "Not Interested"),
    )

    student = models.OneToOneField(
        PreApplication,
        on_delete=models.CASCADE,
        related_name="enquiry_analytics"
    )

    enquiry_token = models.CharField(
        max_length=12,
        unique=True,
        editable=False
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="received"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        if not self.enquiry_token:

            random_number = random.randint(100000, 999999)
            self.enquiry_token = f"ENQ{random_number}"

        super().save(*args, **kwargs)

    def __str__(self):

        return f"{self.enquiry_token} - {self.student.first_name}"