from django.db import models
from django.contrib.auth.models import User

class Company(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='companies')
    name = models.CharField(max_length=255)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Job(models.Model):
    EMPLOYMENT_TYPES = [
        ('FT', 'Full-time'),
        ('PT', 'Part-time'),
        ('CON', 'Contract'),
        ('TEMP', 'Temporary'),
        ('PRN', 'Casual / PRN'),
        ('INT', 'Internship'),
    ]
    REMOTE_CHOICES = [
        ('ONSITE', 'On-site'),
        ('REMOTE', 'Remote'),
        ('HYBRID', 'Hybrid'),
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    province = models.CharField(max_length=120)
    employment_type = models.CharField(max_length=10, choices=EMPLOYMENT_TYPES)
    remote_type = models.CharField(max_length=10, choices=REMOTE_CHOICES, default='ONSITE')
    description = models.TextField()
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} @ {self.company.name}"

class Application(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('REVIEWED', 'Reviewed'),
        ('INTERVIEW', 'Interview'),
        ('REJECTED', 'Rejected'),
        ('HIRED', 'Hired'),
    ]
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    resume_text = models.TextField()
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'applicant')

    def __str__(self):
        return f"{self.applicant.username} -> {self.job.title}"
