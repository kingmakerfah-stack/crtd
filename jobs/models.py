from django.db import models
class Job(models.Model):
    JOB_MODE_CHOICES = [
        ("Remote", "Remote"),
        ("Hybrid", "Hybrid"),
        ("On-site", "On-site"),
    ]
    job_role = models.CharField(max_length=255)
    package = models.DecimalField(max_digits=10, decimal_places=2)
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