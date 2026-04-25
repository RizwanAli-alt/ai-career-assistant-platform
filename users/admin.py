from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import UserProfile, PasswordReset


class UserProfileInline(admin.StackedInline):
    """Inline display of UserProfile in User admin"""
    model = UserProfile
    fields = (
        'bio', 'phone', 'location', 'role',
        'job_preference', 'skills',
        'profile_picture', 'is_email_verified',
        'target_job_titles', 'preferred_locations',
        'expected_salary_min', 'expected_salary_max',
        'cv_score', 'cv_last_analyzed',
        'job_alerts_enabled', 'auto_apply_enabled'
    )
    extra = 0
    readonly_fields = ('cv_score', 'cv_last_analyzed', 'created_at', 'updated_at')


# ✅ UNREGISTER the default User admin first
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with profile information"""
    list_display = (
        'username',
        'email',
        'get_full_name',
        'get_user_role',
        'get_cv_score',
        'is_active',
        'last_login',
    )
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'date_joined',
        'last_login',
        'profile__role',
        'profile__is_email_verified',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'profile__phone')
    ordering = ('-date_joined',)
    inlines = [UserProfileInline]
    
    # Keep default fieldsets and add our custom display methods
    
    def get_full_name(self, obj):
        """Display user's full name"""
        full_name = obj.get_full_name()
        return full_name if full_name else '—'
    get_full_name.short_description = 'Full Name'
    
    def get_user_role(self, obj):
        """Display user role with color badge"""
        if hasattr(obj, 'profile'):
            role = obj.profile.get_role_display()
            color_map = {
                'student': '#17a2b8',
                'graduate': '#28a745',
                'professional': '#ffc107'
            }
            color = color_map.get(obj.profile.role, '#6c757d')
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
                color, role
            )
        return '—'
    get_user_role.short_description = 'Role'
    
    def get_cv_score(self, obj):
        """Display latest CV score"""
        if hasattr(obj, 'profile') and obj.profile.cv_score:
            score = obj.profile.cv_score
            if score >= 80:
                color = '#28a745'
            elif score >= 60:
                color = '#ffc107'
            else:
                color = '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}/100</span>',
                color, score
            )
        return '—'
    get_cv_score.short_description = 'CV Score'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for user profiles"""
    list_display = (
        'user_username',
        'role',
        'get_cv_score_display',
        'job_alerts_enabled',
        'auto_apply_enabled',
        'is_email_verified',
        'updated_at',
    )
    list_filter = (
        'role',
        'is_email_verified',
        'job_alerts_enabled',
        'auto_apply_enabled',
        'created_at',
    )
    search_fields = (
        'user__username',
        'user__email',
        'phone',
        'location',
        'job_preference'
    )
    readonly_fields = (
        'user',
        'cv_score',
        'cv_last_analyzed',
        'created_at',
        'updated_at',
        'get_cv_analysis_link'
    )
    ordering = ('-updated_at',)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'get_cv_analysis_link')
        }),
        ('Personal Details', {
            'fields': ('bio', 'phone', 'location', 'role', 'profile_picture')
        }),
        ('Career Information', {
            'fields': (
                'job_preference',
                'target_job_titles',
                'preferred_locations',
                'skills',
                'expected_salary_min',
                'expected_salary_max'
            )
        }),
        ('CV Analysis', {
            'fields': (
                'latest_cv_analysis',
                'cv_score',
                'cv_last_analyzed'
            ),
            'classes': ('collapse',)
        }),
        ('Job Search & Automation', {
            'fields': (
                'last_job_search',
                'job_alerts_enabled',
                'auto_apply_enabled'
            )
        }),
        ('Account Status', {
            'fields': ('is_email_verified',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_username(self, obj):
        """Display username with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_username.short_description = 'Username'
    
    def get_cv_score_display(self, obj):
        """Display CV score with color"""
        if obj.cv_score:
            if obj.cv_score >= 80:
                color = '#28a745'
            elif obj.cv_score >= 60:
                color = '#ffc107'
            else:
                color = '#dc3545'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}/100</span>',
                color, obj.cv_score
            )
        return '—'
    get_cv_score_display.short_description = 'CV Score'
    
    def get_cv_analysis_link(self, obj):
        """Display link to latest CV analysis"""
        from cv_analyzer.models import CVAnalysis
        try:
            cv = CVAnalysis.objects.filter(user=obj.user).latest('created_at')
            if cv:
                url = reverse('admin:cv_analyzer_cvanalysis_change', args=[cv.id])
                return format_html('<a href="{}" target="_blank">View Latest Analysis</a>', url)
        except CVAnalysis.DoesNotExist:
            pass
        return '—'
    get_cv_analysis_link.short_description = 'Latest CV Analysis'


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    """Admin interface for password reset tokens"""
    list_display = (
        'user_username',
        'is_used',
        'created_at',
        'expires_at',
        'get_expiry_status'
    )
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('user', 'token', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Token Information', {
            'fields': ('user', 'token', 'is_used')
        }),
        ('Dates', {
            'fields': ('created_at', 'expires_at')
        }),
    )
    
    def user_username(self, obj):
        """Display username with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_username.short_description = 'User'
    
    def get_expiry_status(self, obj):
        """Show if token is expired"""
        from django.utils import timezone
        if timezone.now() > obj.expires_at:
            return format_html('<span style="color: #dc3545;">Expired</span>')
        return format_html('<span style="color: #28a745;">Valid</span>')
    get_expiry_status.short_description = 'Status'