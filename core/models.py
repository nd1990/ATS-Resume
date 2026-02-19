from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('RECRUITER', 'Recruiter'),
        ('AGENCY', 'Agency'),
        ('CLIENT_ADMIN', 'Client Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='RECRUITER')
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"

