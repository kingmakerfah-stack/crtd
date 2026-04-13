from django.db import models
class Job(models.Model):
    JOB_MODE_CHOICES = [
        ("Remote", "Remote"),
        ("Hybrid", "Hybrid"),
        ("On-site", "On-site"),
    ]
    job_role = models.CharField(max_length=255)
    package = models.CharField(max_length=20)
    department = models.CharField(max_length=255)
    total_vacancies = models.PositiveIntegerField()
    experience = models.CharField(max_length=100)
    location = models.CharField(max_length=255)

    job_mode = models.CharField(max_length=20, choices=JOB_MODE_CHOICES)

    job_description = models.TextField()
    skills_required = models.TextField()
    eligibility = models.TextField()

    def __str__(self):
        return self.job_role


class Testimonial(models.Model):
    STATUS_PUBLISHED = "published"
    STATUS_DRAFT = "draft"
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "Published"),
        (STATUS_DRAFT, "Draft"),
    ]

    RATING_CHOICES = [
        ("1 Star", "1 Star"),
        ("2 Star", "2 Star"),
        ("3 Star", "3 Star"),
        ("4 Star", "4 Star"),
        ("5 Star", "5 Star"),
    ]

    name = models.CharField(max_length=255)
    profile = models.CharField(max_length=255)
    feedback = models.TextField()
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="5 Star")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name