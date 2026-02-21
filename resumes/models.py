from django.db import models
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
import os
from core.utils import encrypt_content, decrypt_content
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
    semantic_score = models.FloatField(default=0.0, help_text="Semantic similarity score (0-100)")
    
    missing_skills = models.JSONField(default=list)
    matched_skills = models.JSONField(default=list)
    
    ai_explanation = models.TextField(blank=True, help_text="AI generated explanation")
    
    classification = models.CharField(max_length=20, choices=STATUS_CHOICES, default='MAYBE')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('resume', 'job')

class CandidateProfile(models.Model):
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('COMPLIANCE_PENDING', 'Compliance Pending'),
        ('EVALUATED', 'Evaluated'),
        ('SENT_TO_CLIENT', 'Sent to Client'),
    ]

    candidate_name = models.CharField(max_length=255)
    email = models.EmailField()
    current_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='SUBMITTED')
    
    # RBAC fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_profiles')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_profiles')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidate_name} ({self.current_status})"

class ProfileVersion(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    file = models.FileField(upload_to='secure_resumes/')
    changelog = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-version_number']

    def save(self, *args, **kwargs):
        if not self.pk and self.file:
            # Encrypt content before saving
            try:
                # Read content from the file
                content = self.file.read()
                # Encrypt the content
                encrypted_content = encrypt_content(content)
                # Replace the file content with encrypted content
                # We reuse the filename
                self.file = ContentFile(encrypted_content, name=self.file.name)
            except Exception as e:
                # Handle error or log it. For now, pass to let it fail if needed or save unencrypted (bad)
                # Better to raise error
                raise e
        super().save(*args, **kwargs)

    def get_decrypted_file(self):
        """Returns decrypted file content."""
        if self.file:
            self.file.open('rb')
            content = self.file.read()
            self.file.close()
            return decrypt_content(content)
        return None

class SubmissionActivity(models.Model):
    profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255) # e.g., "Uploaded new version", "Changed status"
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']


class ScanRun(models.Model):
    """One batch: JD + multiple resumes scanned together."""
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scan_runs')
    jd_text = models.TextField(help_text="Job description used for matching")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ScanRun {self.id} ({self.created_at.date()})"


class ScanResult(models.Model):
    """Per-candidate result: all AI match + quality check + report data."""
    scan_run = models.ForeignKey(ScanRun, on_delete=models.CASCADE, related_name='results')
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='scan_results')
    candidate_name = models.CharField(max_length=255, blank=True)
    # Scores
    document_quality_score = models.FloatField(default=0.0)
    document_quality_label = models.CharField(max_length=255, blank=True)
    skill_match_percentage = models.FloatField(default=0.0)
    experience_match_score = models.FloatField(default=0.0)
    experience_notes = models.TextField(blank=True)
    certification_status = models.CharField(max_length=255, blank=True)
    certification_details = models.TextField(blank=True)
    compliance_issues = models.JSONField(default=list)
    risk_flags = models.JSONField(default=list)
    final_weighted_score = models.FloatField(default=0.0)
    recommendation = models.CharField(max_length=20, blank=True)  # Hire / Hold / Reject
    qa_grade = models.CharField(max_length=5, blank=True)  # A / B / C / D
    qa_verdict = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-final_weighted_score']

    def __str__(self):
        return f"{self.candidate_name} - {self.final_weighted_score}%"

