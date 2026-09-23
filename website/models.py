from django.conf import settings
from django.db import models


class Profile(models.Model):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        EMPLOYER = "employer", "Employer"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
