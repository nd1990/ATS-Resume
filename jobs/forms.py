from django import forms
from .models import JobRequirement


class JobRequirementForm(forms.ModelForm):
    required_skills_input = forms.CharField(
        label="Required Skills",
        help_text="Comma-separated list of skills (e.g. Python, Django, SQL)",
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Python, Django, REST APIs, PostgreSQL'})
    )
    preferred_skills_input = forms.CharField(
        label="Preferred Skills (Optional)",
        help_text="Comma-separated list of preferred skills",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Docker, AWS, Redis'})
    )
    mandatory_certifications_input = forms.CharField(
        label="Mandatory Certifications (Optional)",
        help_text="Comma-separated list of mandatory certifications",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'AWS Certified, PMP, CISSP'})
    )
    compliance_requirements_input = forms.CharField(
        label="Compliance Requirements (Optional)",
        help_text="Comma-separated compliance requirements (e.g. GDPR, HIPAA)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'GDPR, SOC2, HIPAA'})
    )

    class Meta:
        model = JobRequirement
        fields = [
            'title', 'description', 'experience_years',
            'location', 'industry_domain', 'is_template', 'file'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Senior Backend Engineer'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Remote, New York, NY'}),
            'industry_domain': forms.TextInput(attrs={'placeholder': 'e.g. FinTech, HealthTech, SaaS'}),
        }
        labels = {
            'file': 'Upload JD File (Optional, PDF/DOCX)',
            'is_template': 'Save as reusable template',
        }

    def clean(self):
        cleaned_data = super().clean()

        def parse_csv(field_name):
            val = cleaned_data.get(field_name, '')
            return [s.strip() for s in val.split(',') if s.strip()]

        cleaned_data['required_skills'] = parse_csv('required_skills_input')
        cleaned_data['preferred_skills'] = parse_csv('preferred_skills_input')
        cleaned_data['mandatory_certifications'] = parse_csv('mandatory_certifications_input')
        cleaned_data['compliance_requirements'] = parse_csv('compliance_requirements_input')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.required_skills = self.cleaned_data['required_skills']
        instance.preferred_skills = self.cleaned_data.get('preferred_skills', [])
        instance.mandatory_certifications = self.cleaned_data.get('mandatory_certifications', [])
        instance.compliance_requirements = self.cleaned_data.get('compliance_requirements', [])
        if commit:
            instance.save()
        return instance
