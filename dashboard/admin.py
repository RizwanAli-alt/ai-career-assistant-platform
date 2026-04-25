from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import UserActivity, UserStats, GoalTracker


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """Admin interface for User Activity"""
    list_display = (
        'user_link',
        'get_activity_type_icon',
        'description_short',
        'created_at'
    )
    list_filter = ('activity_type', 'created_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('user', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User & Activity', {
            'fields': ('user', 'activity_type')
        }),
        ('Description', {
            'fields': ('description', 'related_object_id')
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
    
    def get_activity_type_icon(self, obj):
        """Display activity type with emoji"""
        emojis = {
            'cv_analysis': '📊 CV Analysis',
            'job_applied': '📝 Job Applied',
            'job_saved': '💾 Job Saved',
            'forum_post': '💬 Forum Post',
            'profile_updated': '👤 Profile Updated',
            'cv_uploaded': '📄 CV Uploaded'
        }
        return emojis.get(obj.activity_type, obj.get_activity_type_display())
    get_activity_type_icon.short_description = 'Activity'
    
    def description_short(self, obj):
        """Display shortened description"""
        desc = obj.description[:50]
        if len(obj.description) > 50:
            desc += '...'
        return desc
    description_short.short_description = 'Description'


@admin.register(UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    """Admin interface for User Statistics"""
    list_display = (
        'user_link',
        'total_job_applications',
        'saved_jobs_count',
        'cv_analyses_count',
        'forum_posts_count',
        'get_progress_display',
        'last_job_applied'
    )
    list_filter = ('updated_at', 'last_job_applied', 'last_cv_analyzed')
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'user',
        'updated_at',
        'get_progress_bar'
    )
    ordering = ('-updated_at',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Counters', {
            'fields': (
                'total_job_applications',
                'saved_jobs_count',
                'cv_analyses_count',
                'forum_posts_count'
            )
        }),
        ('Goals', {
            'fields': (
                'monthly_applications_goal',
                'weekly_applications_goal',
                'get_progress_bar'
            )
        }),
        ('Last Activities', {
            'fields': (
                'last_job_applied',
                'last_cv_analyzed',
                'last_profile_update'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_progress_display(self, obj):
        """Display progress percentage"""
        progress = obj.get_applications_progress()
        if progress >= 100:
            color = '#28a745'
        elif progress >= 70:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, progress
        )
    get_progress_display.short_description = 'Progress'
    
    def get_progress_bar(self, obj):
        """Display visual progress bar"""
        progress = obj.get_applications_progress()
        return format_html(
            '<div style="width: 100%; background-color: #e9ecef; border-radius: 5px; overflow: hidden;">'
            '<div style="width: {}%; background-color: #28a745; height: 20px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">{}/{} ({}%)</div>'
            '</div>',
            min(progress, 100),
            obj.get_applications_progress(),
            obj.monthly_applications_goal,
            progress
        )
    get_progress_bar.short_description = 'Monthly Progress'


@admin.register(GoalTracker)
class GoalTrackerAdmin(admin.ModelAdmin):
    """Admin interface for Career Goals"""
    list_display = (
        'user_link',
        'title',
        'get_status_badge',
        'get_progress_bar_small',
        'target_date',
        'created_at'
    )
    list_filter = ('status', 'target_date', 'created_at')
    search_fields = ('user__username', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'get_days_remaining')
    ordering = ('target_date',)
    
    fieldsets = (
        ('User & Goal', {
            'fields': ('user', 'title')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status & Progress', {
            'fields': (
                'status',
                'progress_percentage',
                'get_progress_bar_small'
            )
        }),
        ('Timeline', {
            'fields': (
                'target_date',
                'get_days_remaining'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
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
            'active': '#28a745',
            'completed': '#0c5460',
            'paused': '#ffc107',
            'cancelled': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'
    
    def get_progress_bar_small(self, obj):
        """Display small progress bar"""
        progress = obj.progress_percentage
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background-color: #0c5460; height: 15px;"></div>'
            '</div> {}%',
            min(progress, 100), progress
        )
    get_progress_bar_small.short_description = 'Progress'
    
    def get_days_remaining(self, obj):
        """Display days remaining until target date"""
        from django.utils import timezone
        delta = obj.target_date - timezone.now().date()
        days = delta.days
        
        if days < 0:
            color = '#dc3545'
            status = f'Overdue by {-days} days'
        elif days == 0:
            color = '#ffc107'
            status = 'Due Today'
        elif days <= 7:
            color = '#fd7e14'
            status = f'{days} days left'
        else:
            color = '#28a745'
            status = f'{days} days left'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    get_days_remaining.short_description = 'Days Remaining'