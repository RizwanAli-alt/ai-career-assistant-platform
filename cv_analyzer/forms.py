from django import forms
from .models import CVAnalysis, CVTemplate, CVFeedback


class CVUploadForm(forms.ModelForm):
    """
    Form for uploading CV for analysis with job description matching
    
    ✅ NEW FEATURES:
    - Optional job description field for similarity scoring
    - Rich validation messages
    - Help text for users
    """
    
    job_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Paste job description for CV-Job similarity scoring (optional)...',
            'help_text': 'Paste a job description to get a similarity score between your CV and the role.'
        }),
        label='Job Description (Optional)',
        help_text='Paste a job description to see how well your CV matches the role.'
    )
    
    class Meta:
        model = CVAnalysis
        fields = ['cv_file']
        widgets = {
            'cv_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx',
                'id': 'cv_file_input',
            })
        }
        labels = {
            'cv_file': 'Upload Your CV'
        }
        help_texts = {
            'cv_file': 'Supported formats: PDF, DOC, DOCX (Max 5MB). Your file will be analyzed using AI.'
        }
    
    def clean_cv_file(self):
        """Validate CV file - extension, size, and integrity"""
        file = self.cleaned_data.get('cv_file')
        if file:
            allowed_extensions = ['pdf', 'doc', 'docx']
            file_extension = file.name.split('.')[-1].lower()
            
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(
                    f'❌ File type ".{file_extension}" is not supported. '
                    f'Please upload a PDF or DOCX file.'
                )
            
            if file.size > 5 * 1024 * 1024:  # 5MB
                file_size_mb = round(file.size / (1024 * 1024), 2)
                raise forms.ValidationError(
                    f'❌ File is too large ({file_size_mb}MB). '
                    f'Maximum allowed size is 5MB.'
                )
            
            # Check for minimum file size (at least 10KB)
            if file.size < 10 * 1024:
                raise forms.ValidationError(
                    '❌ File is too small. Please upload a valid CV file.'
                )
        
        return file
    
    def clean_job_description(self):
        """Validate job description if provided"""
        job_desc = self.cleaned_data.get('job_description')
        if job_desc and len(job_desc.strip()) < 20:
            raise forms.ValidationError(
                '❌ Job description is too short. Please provide at least 20 characters.'
            )
        return job_desc


class CVComparisonForm(forms.Form):
    """
    Form for comparing two CVs side-by-side
    
    ✅ FEATURES:
    - Dynamic queryset filtering per user
    - Clear labeling
    """
    cv_analysis_1 = forms.ModelChoiceField(
        queryset=CVAnalysis.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'cv_analysis_1',
        }),
        label='First CV',
        help_text='Select the first CV to compare'
    )
    cv_analysis_2 = forms.ModelChoiceField(
        queryset=CVAnalysis.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'cv_analysis_2',
        }),
        label='Second CV',
        help_text='Select the second CV to compare'
    )
    
    def __init__(self, user=None, *args, **kwargs):
        """Filter CVs by user"""
        super().__init__(*args, **kwargs)
        if user:
            self.fields['cv_analysis_1'].queryset = CVAnalysis.objects.filter(
                user=user,
                is_analyzed=True
            ).order_by('-created_at')
            self.fields['cv_analysis_2'].queryset = CVAnalysis.objects.filter(
                user=user,
                is_analyzed=True
            ).order_by('-created_at')
    
    def clean(self):
        """Ensure two different CVs are selected"""
        cleaned_data = super().clean()
        cv1 = cleaned_data.get('cv_analysis_1')
        cv2 = cleaned_data.get('cv_analysis_2')
        
        if cv1 and cv2 and cv1.id == cv2.id:
            raise forms.ValidationError(
                '❌ Please select two different CVs to compare.'
            )
        
        return cleaned_data


class CVFilterForm(forms.Form):
    """
    Form for filtering and sorting CV analyses
    
    ✅ FEATURES:
    - Score range filtering
    - Multiple sort options
    - Professional UI
    """
    SORT_CHOICES = [
        ('latest', '📅 Latest First'),
        ('oldest', '📅 Oldest First'),
        ('highest_score', '📊 Highest Score'),
        ('lowest_score', '📊 Lowest Score'),
        ('best_improvement', '⬆️ Best Improvement'),
    ]
    
    score_min = forms.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Score (0)',
            'id': 'score_min',
        }),
        label='Minimum Score',
        help_text='Filter CVs with score >= this value'
    )
    
    score_max = forms.IntegerField(
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Score (100)',
            'id': 'score_max',
        }),
        label='Maximum Score',
        help_text='Filter CVs with score <= this value'
    )
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='latest',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'sort_by',
        }),
        label='Sort By'
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '🔍 Search...',
            'id': 'search',
        }),
        label='Search',
        help_text='Search by date or file name'
    )
    
    def clean(self):
        """Validate score ranges"""
        cleaned_data = super().clean()
        score_min = cleaned_data.get('score_min')
        score_max = cleaned_data.get('score_max')
        
        if score_min is not None and score_max is not None:
            if score_min > score_max:
                raise forms.ValidationError(
                    '❌ Minimum score cannot be greater than maximum score.'
                )
        
        return cleaned_data


class CVFeedbackForm(forms.ModelForm):
    """
    Form for storing user feedback on CV analysis
    
    ✅ NEW: Allows users to provide feedback on analysis accuracy
    """
    feedback_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Tell us what could be improved...'
        }),
        label='Your Feedback',
        required=False,
        help_text='Your feedback helps us improve the CV analyzer'
    )
    
    is_helpful = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Was this analysis helpful?',
        required=False
    )
    
    class Meta:
        model = CVFeedback
        fields = ['feedback_type', 'severity']
        widgets = {
            'feedback_type': forms.Select(attrs={'class': 'form-control'}),
            'severity': forms.Select(attrs={'class': 'form-control'}),
        }


class JobDescriptionUploadForm(forms.Form):
    """
    Form for uploading/pasting job description for CV matching
    
    ✅ NEW: Separate form for job description matching without re-uploading CV
    """
    job_description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Paste job description here...',
        }),
        label='Job Description',
        help_text='Paste the job description to see how well your CV matches',
        max_length=5000
    )
    
    job_title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Senior Python Developer',
        }),
        label='Job Title (Optional)',
        help_text='Optional: helps categorize the match'
    )
    
    company = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Google, Amazon',
        }),
        label='Company (Optional)',
        help_text='Optional: helps provide company-specific insights'
    )
    
    def clean_job_description(self):
        """Validate job description"""
        job_desc = self.cleaned_data.get('job_description')
        if job_desc and len(job_desc.strip()) < 50:
            raise forms.ValidationError(
                '❌ Job description is too short. Please provide at least 50 characters.'
            )
        return job_desc