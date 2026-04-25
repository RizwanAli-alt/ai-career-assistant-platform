from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import (
    Company, Job, JobApplication, SavedJob, JobAlert,
    JobMatchScore, AutoApplyPermission, ApplicationQueue, AuditLog
)


class JobInline(admin.TabularInline):
    """Inline jobs for Company admin"""
    model = Job
    extra = 0
    fields = ('title', 'status', 'posted_date', 'applicants_count')
    readonly_fields = ('posted_date', 'applicants_count')
    can_delete = False


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin interface for Companies"""
    list_display = (
        'name',
        'get_logo',
        'industry',
        'location',
        'company_size',
        'get_jobs_count',
        'website_link'
    )
    list_filter = ('company_size', 'industry', 'location', 'created_at')
    search_fields = ('name', 'industry', 'location', 'website')
    readonly_fields = ('created_at', 'get_logo')
    ordering = ('name',)
    inlines = [JobInline]
    
    fieldsets = (
        ('Company Information', {
            'fields': ('name', 'description')
        }),
        ('Details', {
            'fields': ('industry', 'location', 'company_size', 'website')
        }),
        ('Branding', {
            'fields': ('logo', 'get_logo')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_logo(self, obj):
        """Display company logo"""
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px; border-radius: 5px;" />',
                obj.logo.url
            )
        return '—'
    get_logo.short_description = 'Logo'
    
    def get_jobs_count(self, obj):
        """Display count of active jobs"""
        count = obj.jobs.filter(status='active').count()
        return format_html('<strong style="color: #0c5460;">{}</strong> jobs', count)
    get_jobs_count.short_description = 'Active Jobs'
    
    def website_link(self, obj):
        """Display website as clickable link"""
        if obj.website:
            return format_html(
                '<a href="{}" target="_blank">🌐 Visit Website</a>',
                obj.website
            )
        return '—'
    website_link.short_description = 'Website'


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin interface for Jobs"""
    list_display = (
        'title',
        'company',
        'location',
        'get_status_badge',
        'experience_level',
        'get_salary_display',
        'get_applications_count',
        'posted_date'
    )
    list_filter = (
        'status',
        'job_type',
        'experience_level',
        'company',
        'posted_date',
    )
    search_fields = ('title', 'description', 'company__name', 'location', 'required_skills')
    readonly_fields = ('posted_date', 'updated_at', 'views_count', 'applicants_count')
    ordering = ('-posted_date',)
    
    fieldsets = (
        ('Job Information', {
            'fields': ('title', 'description', 'company')
        }),
        ('Details', {
            'fields': (
                'job_type',
                'experience_level',
                'location',
                'status'
            )
        }),
        ('Salary', {
            'fields': ('salary_min', 'salary_max', 'currency')
        }),
        ('Requirements', {
            'fields': ('required_skills', 'preferred_skills', 'years_experience')
        }),
        ('Dates', {
            'fields': ('posted_date', 'deadline', 'updated_at')
        }),
        ('Engagement', {
            'fields': ('views_count', 'applicants_count'),
            'classes': ('collapse',)
        }),
    )
    
    def get_status_badge(self, obj):
        """Display status as color badge"""
        colors = {
            'active': '#28a745',
            'closed': '#dc3545',
            'archived': '#6c757d'
        }
        color = colors.get(obj.status, '#0c5460')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'
    
    def get_salary_display(self, obj):
        """Display salary range"""
        if obj.salary_min and obj.salary_max:
            return f'{obj.currency} {obj.salary_min:,} - {obj.salary_max:,}'
        elif obj.salary_min:
            return f'{obj.currency} {obj.salary_min:,}+'
        elif obj.salary_max:
            return f'Up to {obj.currency} {obj.salary_max:,}'
        return '—'
    get_salary_display.short_description = 'Salary'
    
    def get_applications_count(self, obj):
        """Display application count with color"""
        count = obj.applicants_count
        if count > 50:
            color = '#dc3545'
        elif count > 20:
            color = '#fd7e14'
        else:
            color = '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span> applications',
            color, count
        )
    get_applications_count.short_description = 'Applications'


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    """Admin interface for Job Applications"""
    list_display = (
        'user_link',
        'job',
        'get_status_badge',
        'applied_date',
        'viewed_by_company',
        'get_days_ago'
    )
    list_filter = (
        'status',
        'applied_date',
        'viewed_by_company',
    )
    search_fields = ('user__username', 'user__email', 'job__title')
    readonly_fields = ('applied_date', 'updated_at', 'user', 'job')
    ordering = ('-applied_date',)
    
    fieldsets = (
        ('Application Info', {
            'fields': ('user', 'job', 'status')
        }),
        ('Content', {
            'fields': ('cover_letter', 'resume_used')
        }),
        ('Tracking', {
            'fields': ('viewed_by_company', 'viewed_date')
        }),
        ('Dates', {
            'fields': ('applied_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_status_badge(self, obj):
        """Display status badge"""
        colors = {
            'applied': '#0c5460',
            'reviewed': '#0b7dda',
            'shortlisted': '#28a745',
            'interview': '#ffc107',
            'rejected': '#dc3545',
            'accepted': '#17a745'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'
    
    def get_days_ago(self, obj):
        """Display days since application"""
        from django.utils import timezone
        days = (timezone.now() - obj.applied_date).days
        if days == 0:
            return 'Today'
        elif days == 1:
            return 'Yesterday'
        return f'{days} days ago'
    get_days_ago.short_description = 'Applied'


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    """Admin interface for Saved Jobs"""
    list_display = ('user_link', 'job', 'saved_date', 'has_notes')
    list_filter = ('saved_date', 'job__company')
    search_fields = ('user__username', 'job__title', 'notes')
    readonly_fields = ('saved_date',)
    ordering = ('-saved_date',)
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def has_notes(self, obj):
        """Display if notes exist"""
        return '📝 Yes' if obj.notes else '—'
    has_notes.short_description = 'Has Notes'


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    """Admin interface for Job Alerts"""
    list_display = (
        'user_link',
        'title',
        'get_frequency_display',
        'is_active_badge',
        'last_sent',
        'created_at'
    )
    list_filter = ('is_active', 'frequency', 'created_at')
    search_fields = ('user__username', 'title', 'keywords')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Alert Info', {
            'fields': ('user', 'title', 'is_active')
        }),
        ('Criteria', {
            'fields': ('keywords', 'location', 'job_type', 'experience_level')
        }),
        ('Settings', {
            'fields': ('frequency', 'last_sent')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def is_active_badge(self, obj):
        """Display active status"""
        color = '#28a745' if obj.is_active else '#dc3545'
        status = '✅ Active' if obj.is_active else '❌ Inactive'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, status
        )
    is_active_badge.short_description = 'Status'
    
    def get_frequency_display(self, obj):
        """Display frequency with emoji"""
        emojis = {'daily': '📅', 'weekly': '📆', 'instant': '⚡'}
        emoji = emojis.get(obj.frequency, '📧')
        return f'{emoji} {obj.get_frequency_display()}'
    get_frequency_display.short_description = 'Frequency'


@admin.register(JobMatchScore)
class JobMatchScoreAdmin(admin.ModelAdmin):
    """Admin interface for Job Match Scores"""
    list_display = (
        'user_link',
        'job',
        'get_overall_match_display',
        'skills_match',
        'experience_match',
        'calculated_at'
    )
    list_filter = ('calculated_at',)
    search_fields = ('user__username', 'job__title')
    readonly_fields = ('user', 'job', 'calculated_at', 'match_reasons')
    ordering = ('-calculated_at',)
    
    fieldsets = (
        ('Matching Info', {
            'fields': ('user', 'job')
        }),
        ('Scores', {
            'fields': (
                'overall_match',
                'skills_match',
                'experience_match',
                'location_match'
            )
        }),
        ('Details', {
            'fields': ('match_reasons',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('calculated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_overall_match_display(self, obj):
        """Display overall match score with color"""
        score = obj.overall_match
        if score >= 80:
            color = '#28a745'
        elif score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, score
        )
    get_overall_match_display.short_description = 'Overall Match'


@admin.register(AutoApplyPermission)
class AutoApplyPermissionAdmin(admin.ModelAdmin):
    """Admin interface for Auto-Apply Permissions"""
    list_display = (
        'user_link',
        'allowed_badge',
        'daily_limit',
        'require_approval',
        'terms_accepted',
        'granted_at'
    )
    list_filter = ('allowed', 'require_approval', 'terms_accepted', 'granted_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user',)
    ordering = ('user',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Permissions', {
            'fields': ('allowed', 'require_approval', 'terms_accepted')
        }),
        ('Settings', {
            'fields': ('daily_limit', 'granted_at')
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def allowed_badge(self, obj):
        """Display allowed status"""
        color = '#28a745' if obj.allowed else '#dc3545'
        status = '✅ Enabled' if obj.allowed else '❌ Disabled'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, status
        )
    allowed_badge.short_description = 'Status'


@admin.register(ApplicationQueue)
class ApplicationQueueAdmin(admin.ModelAdmin):
    """Admin interface for Application Queue"""
    list_display = (
        'user_link',
        'job',
        'get_status_badge',
        'match_score',
        'queued_at',
        'applied_at'
    )
    list_filter = ('status', 'queued_at', 'applied_at')
    search_fields = ('user__username', 'job__title')
    readonly_fields = ('user', 'job', 'queued_at', 'applied_at')
    ordering = ('-queued_at',)
    
    fieldsets = (
        ('Application Info', {
            'fields': ('user', 'job', 'status')
        }),
        ('Matching', {
            'fields': ('match_score', 'cover_letter')
        }),
        ('Dates', {
            'fields': ('queued_at', 'applied_at')
        }),
        ('Details', {
            'fields': ('failure_reason',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_status_badge(self, obj):
        """Display status badge"""
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'submitted': '#0c5460',
            'failed': '#fd7e14'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Audit Logs (Read-Only)"""
    list_display = (
        'user_link',
        'action',
        'get_status_badge',
        'job_link',
        'timestamp'
    )
    list_filter = ('action', 'status', 'timestamp')
    search_fields = ('user__username', 'action', 'detail')
    readonly_fields = ('user', 'job', 'action', 'status', 'detail', 'timestamp')
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Action', {
            'fields': ('user', 'action', 'status')
        }),
        ('References', {
            'fields': ('job',)
        }),
        ('Details', {
            'fields': ('detail',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable adding new audit logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deleting audit logs"""
        return False
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def job_link(self, obj):
        """Display job with link"""
        if obj.job:
            url = reverse('admin:jobs_job_change', args=[obj.job.id])
            return format_html('<a href="{}">{}</a>', url, obj.job.title)
        return '—'
    job_link.short_description = 'Job'
    
    def get_status_badge(self, obj):
        """Display status badge"""
        colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'pending': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.status.upper()
        )
    get_status_badge.short_description = 'Status'