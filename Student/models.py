from django.db import models
from crtd.settings import AUTH_USER_MODEL as User


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True
    )

    enrollment_id = models.CharField(max_length=20, unique=True, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return str(self.user.email) if self.user else "Student"
    
class StudentPersonalDetail(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="personal_detail",
        null=True,
        blank=True
    )

    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    whatsapp_no = models.CharField(max_length=13, null=True, blank=True)
    alternate_phone = models.CharField(max_length=13, null=True, blank=True)

    birthplace_state = models.CharField(max_length=100, null=True, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)

    permanent_state = models.CharField(max_length=100, null=True, blank=True)
    permanent_city = models.CharField(max_length=100, null=True, blank=True)
    permanent_pin_code = models.CharField(max_length=10, null=True, blank=True)
    permanent_address = models.TextField(null=True, blank=True)

    current_state = models.CharField(max_length=100, null=True, blank=True)
    current_city = models.CharField(max_length=100, null=True, blank=True)
    current_pin_code = models.CharField(max_length=10, null=True, blank=True)
    current_address = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name or ''} {self.last_name or ''}"

class StudentEducation(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="education",
        null=True,
        blank=True
    )

    qualification = models.CharField(max_length=100, null=True, blank=True)
    specialization = models.CharField(max_length=100, null=True, blank=True)

    college_name = models.CharField(max_length=150, null=True, blank=True)
    college_state = models.CharField(max_length=100, null=True, blank=True)

    passing_year = models.CharField(max_length=4, null=True, blank=True)

    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    skills = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.student.user.email if self.student and self.student.user else 'Education'}"

class StudentCareerPreference(models.Model):
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="career_preference",
        null=True,
        blank=True
    )

    preferred_job_role = models.CharField(max_length=150, null=True, blank=True)
    work_mode = models.CharField(max_length=50, null=True, blank=True)

    preferred_time = models.CharField(max_length=50, null=True, blank=True)

    experience = models.CharField(max_length=50, null=True, blank=True)
    expected_ctc = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.student.user.email if self.student and self.student.user else 'Career'}"