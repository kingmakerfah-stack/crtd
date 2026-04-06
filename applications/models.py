from django.db import models
from Student.models import Student
from jobs.models import Job
import random 
from django.core.validators import MinValueValidator, MaxValueValidator
class CoolDown(models.Model):
    cooldown_days= models.IntegerField(default=10, validators=[MinValueValidator(0), MaxValueValidator(365)])

    def __str__(self):
        return f"{self.cooldown_days} days cooldown"

class Application(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('hold', 'Hold'),
        ('selected', 'Selected'),
        ('rejected', 'Rejected'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    cooldown_days_used = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(365)])
    reason = models.TextField(null=True,blank=True)
    reference_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    def generate_reference(self):
        part1 = random.randint(1000, 9999)
        part2 = random.randint(100, 999)
        return f"REF-{part1}-{part2}"

    def save(self, *args, **kwargs):
        if not self.reference_id:
            ref = self.generate_reference()

            # ensure uniqueness
            while Application.objects.filter(reference_id=ref).exists():
                ref = self.generate_reference()

            self.reference_id = ref

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ['student', 'job']
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.student} → {self.job} ({self.status})"