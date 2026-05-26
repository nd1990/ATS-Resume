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
        empty_label="-- Optional: Select a Job --",
        required=False,
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
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Paste the job description here",
                "class": "form-control bg-card-bg text-white",
                "style": "resize: vertical;",
            }
        ),
    )
    jd_file = forms.FileField(
        label="Or Upload JD File",
        required=False,
        help_text="Upload the JD as PDF, DOCX, JPG or PNG.",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.docx,.png,.jpg,.jpeg",
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

    def clean(self):
        cleaned_data = super().clean()
        jd_text = (cleaned_data.get('job_description') or '').strip()
        jd_file = cleaned_data.get('jd_file')
        if not jd_text and not jd_file:
            raise forms.ValidationError("Please paste a job description or upload a JD file.")
        return cleaned_data


class AIFilterBatchForm(forms.Form):
    """Batch upload: one JD + multiple resumes for AI filter & quality check."""
    job_description = forms.CharField(
        label="Job Description",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Paste the full job description. All resumes will be matched against this JD.",
                "class": "form-control bg-card-bg text-white",
                "style": "resize: vertical;",
            }
        ),
    )
    jd_file = forms.FileField(
        label="Or Upload JD File",
        required=False,
        help_text="Upload the JD as PDF, DOCX, JPG or PNG.",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.docx,.png,.jpg,.jpeg",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        jd_text = (cleaned_data.get('job_description') or '').strip()
        jd_file = cleaned_data.get('jd_file')
        if not jd_text and not jd_file:
            raise forms.ValidationError("Please paste a job description or upload a JD file.")
        return cleaned_data


class MatchStoredForm(forms.Form):
    """Match stored resumes with a JD: paste JD + select which stored resumes to run QA on."""
    saved_jd = forms.ModelChoiceField(
        queryset=JobRequirement.objects.filter(is_template=True),
        label="Select Saved JD",
        help_text="Pick a previously saved JD to reuse.",
        empty_label="-- Use a new JD below --",
        required=False,
    )
    job_description = forms.CharField(
        label="Job Description",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Paste the job description. Stored resumes will be matched against specs, certificates, and requirements.",
                "class": "form-control bg-card-bg text-white",
                "style": "resize: vertical;",
            }
        ),
    )
    jd_file = forms.FileField(
        label="Or Upload JD File",
        required=False,
        help_text="Upload the JD as PDF, DOCX, JPG or PNG.",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.docx,.png,.jpg,.jpeg",
            }
        ),
    )
    resumes = forms.ModelMultipleChoiceField(
        queryset=Resume.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Select stored resumes to match",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resumes'].queryset = Resume.objects.all().order_by('-uploaded_at')

    def clean(self):
        cleaned_data = super().clean()
        saved_jd = cleaned_data.get('saved_jd')
        jd_text = (cleaned_data.get('job_description') or '').strip()
        jd_file = cleaned_data.get('jd_file')
        if not saved_jd and not jd_text and not jd_file:
            raise forms.ValidationError("Select a saved JD OR paste a job description / upload a JD file.")
        return cleaned_data
