from django import forms
from .models import Resume, CandidateProfile, ProfileVersion
from jobs.models import JobRequirement


class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['file']


class BulkUploadForm(forms.Form):
    job = forms.ModelChoiceField(
        queryset=JobRequirement.objects.all(),
        label="Select Job Role",
        help_text="Resumes will be screened against this job.",
        empty_label="-- Select a Job --"
    )
    # Note: Multiple file input is handled directly in the template HTML.
    # Django's FileField validates a single file; the view reads all
    # uploaded files via request.FILES.getlist('resumes').


class SecureProfileUploadForm(forms.ModelForm):
    file = forms.FileField(label="Resume File (PDF/DOCX)")

    class Meta:
        model = CandidateProfile
        fields = ['candidate_name', 'email']


class CandidateStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ['current_status']


class JDResumeAnalysisForm(forms.Form):
    job_description = forms.CharField(
        label="Job Description",
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Paste the job description here",
                "class": "form-control bg-card-bg text-white",
                "style": "resize: vertical;",
            }
        ),
    )
    candidate_file = forms.FileField(
        label="Candidate Resume File",
        help_text="Upload PDF, DOCX, PNG or JPG.",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.docx,.png,.jpg,.jpeg",
            }
        ),
    )

