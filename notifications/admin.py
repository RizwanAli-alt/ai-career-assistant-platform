from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notifications"""
    list_display = (
        'user_link',
        'get_type_icon',
        'title_preview',
        'read_badge',
        'created_at'
    )
    list_filter = (
        'notification_type',
        'is_read',
        'is_archived',
        'created_at'
    )
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('user', 'created_at', 'read_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Notification Info', {
            'fields': ('user', 'notification_type')
        }),
        ('Content', {
            'fields': ('title', 'message', 'icon')
        }),
        ('Status', {
            'fields': ('is_read', 'is_archived')
        }),
        ('Link', {
            'fields': ('related_url',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'read_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_type_icon(self, obj):
        """Display type with icon"""
        icons = {
            'job_match': '📊 Job Match',
            'application_update': '📝 Application Update',
            'forum_reply': '💬 Forum Reply',
            'message': '✉️ Message',
            'alert': '⚠️ Alert',
            'achievement': '🏆 Achievement'
        }
        return icons.get(obj.notification_type, obj.get_notification_type_display())
    get_type_icon.short_description = 'Type'
    
    def title_preview(self, obj):
        """Display title preview"""
        return obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
    title_preview.short_description = 'Title'
    
    def read_badge(self, obj):
        """Display read status"""
        if obj.is_read:
            return format_html('<span style="color: #6c757d;">✓ Read</span>')
        return format_html('<span style="color: #0b7dda;">● Unread</span>')
    read_badge.short_description = 'Status'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin interface for Notification Preferences"""
    list_display = (
        'user_link',
        'in_app_notifications_badge',
        'email_badges',
        'frequency_badge'
    )
    list_filter = (
        'in_app_notifications',
        'email_on_job_match',
        'email_on_application_update',
        'email_on_forum_reply',
        'notification_frequency'
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'created_at')
    ordering = ('user__username',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('In-App Notifications', {
            'fields': ('in_app_notifications',)
        }),
        ('Email Notifications', {
            'fields': (
                'email_on_job_match',
                'email_on_application_update',
                'email_on_forum_reply'
            )
        }),
        ('Frequency', {
            'fields': ('notification_frequency',)
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
    
    def in_app_notifications_badge(self, obj):
        """Display in-app notification status"""
        color = '#28a745' if obj.in_app_notifications else '#dc3545'
        status = '✅ Enabled' if obj.in_app_notifications else '❌ Disabled'
        return format_html('<span style="color: {};">{}</span>', color, status)
    in_app_notifications_badge.short_description = 'In-App'
    
    def email_badges(self, obj):
        """Display email notification statuses"""
        badges = []
        if obj.email_on_job_match:
            badges.append(format_html('<span style="color: #28a745;">✓ Jobs</span>'))
        if obj.email_on_application_update:
            badges.append(format_html('<span style="color: #28a745;">✓ Applications</span>'))
        if obj.email_on_forum_reply:
            badges.append(format_html('<span style="color: #28a745;">✓ Forum</span>'))
        
        if not badges:
            return format_html('<span style="color: #dc3545;">✗ All Disabled</span>')
        
        return format_html(' | '.join(str(b) for b in badges))
    email_badges.short_description = 'Email Notifications'
    
    def frequency_badge(self, obj):
        """Display frequency"""
        icons = {
            'instant': '⚡ Instant',
            'daily': '📅 Daily',
            'weekly': '📆 Weekly'
        }
        return icons.get(obj.notification_frequency, obj.get_notification_frequency_display())
    frequency_badge.short_description = 'Frequency'