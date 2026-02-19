from django.db import models

class JobRequirement(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.JSONField(default=list, help_text="List of required skills")
    preferred_skills = models.JSONField(default=list, blank=True, help_text="List of preferred skills")
    experience_years = models.IntegerField(default=0)
    keywords = models.JSONField(default=list, blank=True, help_text="AI extraction keywords")
    created_at = models.DateTimeField(auto_now_add=True)

    mandatory_certifications = models.JSONField(default=list, blank=True, help_text="List of mandatory certifications")
    location = models.CharField(max_length=255, blank=True, null=True)
    industry_domain = models.CharField(max_length=255, blank=True, null=True)
    compliance_requirements = models.JSONField(default=list, blank=True, help_text="Regulatory or compliance requirements")
    is_template = models.BooleanField(default=False, help_text="Save as reusable template")
    file = models.FileField(upload_to='jds/', blank=True, null=True, help_text="Original JD file")
    
    def __str__(self):
        return f"{self.title} ({'Template' if self.is_template else 'Job'})"
