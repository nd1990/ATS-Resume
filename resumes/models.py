from django.db import models
from jobs.models import JobRequirement

class Resume(models.Model):
    file = models.FileField(upload_to='resumes/')
    parsed_content = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata
    candidate_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"Resume {self.id} - {self.candidate_name or 'Unknown'}"

class ResumeScore(models.Model):
    STATUS_CHOICES = [
        ('SHORTLISTED', 'Shortlisted'),
        ('MAYBE', 'Maybe'),
        ('REJECTED', 'Rejected'),
    ]

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='scores')
    job = models.ForeignKey(JobRequirement, on_delete=models.CASCADE, related_name='scores')
    
    match_percentage = models.FloatField(help_text="Overall match score (0-100)")
    skill_match_score = models.FloatField(default=0.0)
    
    missing_skills = models.JSONField(default=list)
    matched_skills = models.JSONField(default=list)
    
    ai_explanation = models.TextField(blank=True, help_text="AI generated explanation")
    
    classification = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MAYBE')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('resume', 'job')
