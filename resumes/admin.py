from django.contrib import admin
from .models import Resume, ResumeScore, CandidateProfile, ProfileVersion, SubmissionActivity

admin.site.register(Resume)
admin.site.register(ResumeScore)

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'email', 'current_status', 'created_by', 'assigned_to')
    list_filter = ('current_status', 'created_by')

@admin.register(ProfileVersion)
class ProfileVersionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'version_number', 'created_at', 'created_by')
    readonly_fields = ('file',) # Prevent accidental overwrite without encryption via admin

@admin.register(SubmissionActivity)
class SubmissionActivityAdmin(admin.ModelAdmin):
    list_display = ('profile', 'actor', 'action', 'timestamp')
    list_filter = ('action', 'timestamp')

