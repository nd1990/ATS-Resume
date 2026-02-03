from django.db import models

class JobRequirement(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    required_skills = models.JSONField(default=list, help_text="List of required skills")
    preferred_skills = models.JSONField(default=list, blank=True, help_text="List of preferred skills")
    experience_years = models.IntegerField(default=0)
    keywords = models.JSONField(default=list, blank=True, help_text="AI extraction keywords")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
