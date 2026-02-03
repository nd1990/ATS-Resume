from django import forms
from .models import JobRequirement
import json

class JobRequirementForm(forms.ModelForm):
    required_skills_input = forms.CharField(
        help_text="Comma-separated list of skills (e.g. Python, Django, SQL)",
        required=True,
        widget=forms.Textarea(attrs={'rows': 3})
    )

    class Meta:
        model = JobRequirement
        fields = ['title', 'description', 'experience_years']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned_data = super().clean()
        skills_str = cleaned_data.get('required_skills_input', "")
        # Convert CSV string to list
        skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
        cleaned_data['required_skills'] = skills_list
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.required_skills = self.cleaned_data['required_skills']
        if commit:
            instance.save()
        return instance
