from django.db import models


class EnquiryTokenSequence(models.Model):
    next_value = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Next enquiry token number: {self.next_value}"


class PreApplication(models.Model):
    enquiry_token = models.CharField(
        max_length=9,
        unique=True,
        db_index=True,
        editable=False,
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    whatsapp_no = models.CharField(max_length=13)
    alternate_phone = models.CharField(max_length=13, blank=True, null=True)
    birthplace_state = models.CharField(max_length=100)
    qualification = models.CharField(max_length=100)
    specialization = models.CharField(max_length=100)
    college_name = models.CharField(max_length=150)
    college_state = models.CharField(max_length=100)
    passing_year = models.CharField(max_length=4)
    preferred_time = models.CharField(max_length=50)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            original_token = type(self).objects.filter(pk=self.pk).values_list(
                "enquiry_token",
                flat=True,
            ).first()
            if original_token and self.enquiry_token != original_token:
                raise ValueError("enquiry_token cannot be modified once created.")
        elif not self.enquiry_token:
            from .services import allocate_next_enquiry_token

            self.enquiry_token = allocate_next_enquiry_token()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.enquiry_token} - {self.first_name} {self.last_name}".strip()


class ReferalCode(models.Model):
    student = models.OneToOneField(
        PreApplication,
        on_delete=models.CASCADE,
        related_name="referal_codes",
    )
    code = models.CharField(max_length=10, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} -> {self.student.enquiry_token}"
