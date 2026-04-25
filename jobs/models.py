from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Company(models.Model):
    """Model for job companies"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    location = models.CharField(max_length=200)
    industry = models.CharField(max_length=100)
    company_size = models.CharField(
        max_length=50,
        choices=[
            ('startup', 'Startup'),
            ('small', 'Small (10-50)'),
            ('medium', 'Medium (50-500)'),
            ('large', 'Large (500+)'),
        ],
        default='medium'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'jobs_company'
        verbose_name_plural = 'Companies'
    
    def __str__(self):
        return self.name


class Job(models.Model):
    """Model for job listings"""
    JOB_TYPE_CHOICES = [
        ('full-time', 'Full Time'),
        ('part-time', 'Part Time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
    ]
    
    EXPERIENCE_LEVEL = [
        ('entry', 'Entry Level'),
        ('mid', 'Mid Level'),
        ('senior', 'Senior'),
        ('executive', 'Executive'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]
    
    # Basic Info
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='jobs')
    location = models.CharField(max_length=200)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL)
    
    # Details
    salary_min = models.IntegerField(blank=True, null=True)
    salary_max = models.IntegerField(blank=True, null=True)
    currency = models.CharField(max_length=10, default='USD')
    
    # Requirements
    required_skills = models.TextField()  # Comma-separated
    preferred_skills = models.TextField(blank=True, null=True)
    years_experience = models.IntegerField(default=0)
    
    # Meta
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    posted_date = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Engagement
    views_count = models.IntegerField(default=0)
    applicants_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'jobs_job'
        ordering = ['-posted_date']
        indexes = [
            models.Index(fields=['status', '-posted_date']),
            models.Index(fields=['job_type']),
        ]
    
    def __str__(self):
        return f"{self.title} at {self.company.name}"
    
    def get_required_skills_list(self):
        return [skill.strip() for skill in self.required_skills.split(',')]
    
    def get_preferred_skills_list(self):
        if self.preferred_skills:
            return [skill.strip() for skill in self.preferred_skills.split(',')]
        return []
    
    def is_deadline_passed(self):
        if self.deadline:
            return self.deadline < timezone.now()
        return False
    
    def days_until_deadline(self):
        if self.deadline:
            delta = self.deadline - timezone.now()
            return delta.days
        return None


class JobApplication(models.Model):
    """Model for job applications"""
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview'),
        ('rejected', 'Rejected'),
        ('accepted', 'Accepted'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    
    # Application info
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    cover_letter = models.TextField(blank=True, null=True)
    resume_used = models.FileField(upload_to='application_resumes/', blank=True, null=True)
    
    # Dates
    applied_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking
    viewed_by_company = models.BooleanField(default=False)
    viewed_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'jobs_job_application'
        unique_together = ('user', 'job')
        ordering = ['-applied_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.job.title}"


class SavedJob(models.Model):
    """Model for saved jobs"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by_users')
    saved_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'jobs_saved_job'
        unique_together = ('user', 'job')
        ordering = ['-saved_date']
    
    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"


class JobAlert(models.Model):
    """Model for job alerts"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('instant', 'Instant'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_alerts')
    title = models.CharField(max_length=200)
    keywords = models.CharField(max_length=500)
    location = models.CharField(max_length=200, blank=True, null=True)
    job_type = models.CharField(max_length=20, blank=True, null=True)
    experience_level = models.CharField(max_length=20, blank=True, null=True)
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='weekly')
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'jobs_job_alert'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Alert: {self.title}"


class JobMatchScore(models.Model):
    """Model for job matching scores"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_matches')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='match_scores')
    
    # Matching scores
    skills_match = models.FloatField(default=0)  # 0-100
    experience_match = models.FloatField(default=0)  # 0-100
    location_match = models.FloatField(default=0)  # 0-100
    overall_match = models.FloatField(default=0)  # 0-100
    
    match_reasons = models.TextField(blank=True, null=True)  # JSON format
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'jobs_job_match_score'
        unique_together = ('user', 'job')
    
    def __str__(self):
        return f"{self.user.username} - {self.job.title}: {self.overall_match}%"


# ─── Auto-Apply Agent Models ───────────────────────────────────────────────────

class AutoApplyPermission(models.Model):
    """Controls whether and how auto-apply runs for a user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auto_apply_permission')
    allowed = models.BooleanField(default=False)
    daily_limit = models.IntegerField(default=10)
    require_approval = models.BooleanField(default=True)
    granted_at = models.DateTimeField(null=True, blank=True)
    terms_accepted = models.BooleanField(default=False)

    class Meta:
        db_table = 'jobs_auto_apply_permission'

    def __str__(self):
        return f"{self.user.username} – Auto-Apply {'On' if self.allowed else 'Off'}"


class ApplicationQueue(models.Model):
    """Queued job applications awaiting user approval or submission."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('submitted', 'Submitted'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='application_queue')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='application_queue')
    match_score = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    cover_letter = models.TextField(blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'jobs_application_queue'
        ordering = ['-queued_at']
        unique_together = ('user', 'job')

    def __str__(self):
        return f"{self.user.username} → {self.job.title} [{self.status}]"


class AuditLog(models.Model):
    """Immutable record of every auto-apply action."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'jobs_audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} – {self.action} [{self.status}]"