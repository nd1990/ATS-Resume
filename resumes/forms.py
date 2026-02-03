from django import forms
from .models import Resume
from jobs.models import JobRequirement

class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['file', 'candidate_name', 'email']

class BulkUploadForm(forms.Form):
    job = forms.ModelChoiceField(queryset=JobRequirement.objects.all(), help_text="Select the Job to screen these resumes for")



