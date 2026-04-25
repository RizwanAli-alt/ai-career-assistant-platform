from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extended user profile with CV analyzer integration"""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('graduate', 'Graduate'),
        ('professional', 'Professional'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True, help_text="Tell us about yourself")
    phone = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    cv = models.FileField(upload_to='cvs/', blank=True, null=True)
    cv_uploaded_at = models.DateTimeField(blank=True, null=True)
    job_preference = models.CharField(max_length=200, blank=True, null=True)
    skills = models.TextField(blank=True, null=True, help_text="Comma-separated skills")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    
    # ✅ NEW: CV Analyzer Integration
    latest_cv_analysis = models.OneToOneField(
        'cv_analyzer.CVAnalysis',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_profile',
        help_text="Latest CV analysis for this user"
    )
    cv_score = models.IntegerField(default=0, help_text="Latest CV score (0-100)")
    cv_last_analyzed = models.DateTimeField(null=True, blank=True)
    
    # ✅ NEW: Job Preferences & Matching
    target_job_titles = models.TextField(
        blank=True, null=True,
        help_text="Comma-separated target job titles (e.g., Python Developer, Data Scientist)"
    )
    preferred_locations = models.TextField(
        blank=True, null=True,
        help_text="Comma-separated preferred locations (e.g., Islamabad, Remote, Lahore)"
    )
    expected_salary_min = models.IntegerField(null=True, blank=True, help_text="Minimum expected salary")
    expected_salary_max = models.IntegerField(null=True, blank=True, help_text="Maximum expected salary")
    
    # ✅ NEW: Job Search & Scraper Tracking
    last_job_search = models.DateTimeField(null=True, blank=True)
    job_alerts_enabled = models.BooleanField(default=True)
    auto_apply_enabled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_skills_list(self):
        """Return skills as a list"""
        if self.skills:
            return [skill.strip() for skill in self.skills.split(',') if skill.strip()]
        return []
    
    def get_target_jobs_list(self):
        """Return target job titles as a list"""
        if self.target_job_titles:
            return [job.strip() for job in self.target_job_titles.split(',') if job.strip()]
        return []
    
    def get_preferred_locations_list(self):
        """Return preferred locations as a list"""
        if self.preferred_locations:
            return [loc.strip() for loc in self.preferred_locations.split(',') if loc.strip()]
        return []
    
    # ✅ NEW: Helper methods for job matching
    def has_recent_cv_analysis(self):
        """Check if user has a recent CV analysis (within last 7 days)"""
        from datetime import timedelta
        from django.utils import timezone
        
        if self.cv_last_analyzed:
            return (timezone.now() - self.cv_last_analyzed).days <= 7
        return False
    
    def get_cv_analysis(self):
        """Get the latest CV analysis for this user"""
        from cv_analyzer.models import CVAnalysis
        return CVAnalysis.objects.filter(user=self.user).order_by('-created_at').first()
    
    def get_extracted_skills_from_cv(self):
        """Extract skills from latest CV analysis"""
        import json
        
        cv_analysis = self.latest_cv_analysis
        if cv_analysis and cv_analysis.extracted_skills:
            try:
                skills = json.loads(cv_analysis.extracted_skills)
                return {
                    'technical': skills.get('technical', []),
                    'soft': skills.get('soft', []),
                }
            except (json.JSONDecodeError, TypeError):
                return {'technical': [], 'soft': []}
        return {'technical': [], 'soft': []}
    
    def update_cv_analysis_info(self, analysis):
        """Update profile with latest CV analysis info"""
        self.latest_cv_analysis = analysis
        self.cv_score = analysis.overall_score
        self.cv_last_analyzed = analysis.created_at
        self.save()


class PasswordReset(models.Model):
    """Model for password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'auth_password_reset'
    
    def __str__(self):
        return f"Reset token for {self.user.username}"


# ✅ Signal to create user profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile instance when a User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile instance when the User is saved"""
    instance.profile.save()