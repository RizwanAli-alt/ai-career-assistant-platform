from django import forms
from .models import Job, JobApplication, SavedJob, JobAlert

class JobSearchForm(forms.Form):
    """Form for job search"""
    SORT_CHOICES = [
        ('newest', 'Newest First'),
        ('relevant', 'Most Relevant'),
        ('salary_high', 'Highest Salary'),
        ('salary_low', 'Lowest Salary'),
    ]
    
    keyword = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'job-filter-input',
            'placeholder': 'Job title, keywords...',
            'autocomplete': 'off'
        })
    )
    
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'job-filter-input',
            'placeholder': 'City or country',
            'autocomplete': 'off'
        })
    )
    
    job_type = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('full-time', 'Full Time'),
            ('part-time', 'Part Time'),
            ('contract', 'Contract'),
            ('freelance', 'Freelance'),
            ('internship', 'Internship'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'job-filter-checkbox'
        })
    )
    
    experience_level = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('entry', 'Entry Level'),
            ('mid', 'Mid Level'),
            ('senior', 'Senior'),
            ('executive', 'Executive'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'job-filter-checkbox'
        })
    )
    
    salary_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'job-filter-input',
            'placeholder': 'Min Salary'
        })
    )
    
    salary_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'job-filter-input',
            'placeholder': 'Max Salary'
        })
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'job-filter-input'
        })
    )


class JobApplicationForm(forms.ModelForm):
    """Form for job application"""
    
    class Meta:
        model = JobApplication
        fields = ['cover_letter']
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Tell the employer why you\'re interested in this position...'
            })
        }


class SaveJobForm(forms.ModelForm):
    """Form for saving jobs"""
    
    class Meta:
        model = SavedJob
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add notes about this job...'
            })
        }


class JobAlertForm(forms.ModelForm):
    """Form for creating job alerts"""
    
    class Meta:
        model = JobAlert
        fields = ['title', 'keywords', 'location', 'job_type', 'experience_level', 'frequency']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alert name (e.g., Python Developer)'
            }),
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Comma-separated keywords'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City or remote'
            }),
            'job_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'experience_level': forms.Select(attrs={
                'class': 'form-control'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
