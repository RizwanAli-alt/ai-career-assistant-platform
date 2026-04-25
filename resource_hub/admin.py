from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    ResourceCategory, Resource, UserResourceProgress, SkillPath
)


class ResourceInline(admin.TabularInline):
    """Inline resources for ResourceCategory"""
    model = Resource
    extra = 0
    fields = ('title', 'resource_type', 'difficulty_level', 'featured', 'views_count')
    readonly_fields = ('views_count',)
    can_delete = False


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    """Admin interface for Resource Categories"""
    list_display = ('name', 'get_resources_count', 'order')
    list_filter = ('order',)
    search_fields = ('name', 'description')
    ordering = ('order',)
    inlines = [ResourceInline]
    
    fieldsets = (
        ('Category Info', {
            'fields': ('name', 'description', 'icon', 'order')
        }),
    )
    
    def get_resources_count(self, obj):
        """Display resource count"""
        total = obj.resources.count()
        active = obj.resources.filter(is_active=True).count()
        return format_html(
            '<strong>{}</strong> resources ({} active)',
            total, active
        )
    get_resources_count.short_description = 'Resources'


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Admin interface for Learning Resources"""
    list_display = (
        'title_preview',
        'category',
        'get_type_badge',
        'get_difficulty_badge',
        'featured_badge',
        'get_engagement_display'
    )
    list_filter = (
        'resource_type',
        'difficulty_level',
        'featured',
        'is_active',
        'category',
        'created_at'
    )
    search_fields = ('title', 'description', 'author', 'skills_covered')
    readonly_fields = (
        'created_at',
        'updated_at',
        'views_count',
        'likes_count',
        'get_thumbnail'
    )
    ordering = ('-featured', '-created_at')
    
    fieldsets = (
        ('Resource Info', {
            'fields': ('category', 'title', 'resource_type', 'difficulty_level')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Content', {
            'fields': ('content', 'external_url')
        }),
        ('Media', {
            'fields': ('thumbnail', 'get_thumbnail')
        }),
        ('Metadata', {
            'fields': (
                'author',
                'duration_minutes',
                'skills_covered'
            ),
            'classes': ('collapse',)
        }),
        ('Status & Engagement', {
            'fields': (
                'featured',
                'is_active',
                'views_count',
                'likes_count'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def title_preview(self, obj):
        """Display title preview"""
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_preview.short_description = 'Title'
    
    def get_type_badge(self, obj):
        """Display resource type as badge"""
        colors = {
            'course': '#0c5460',
            'article': '#0b7dda',
            'tutorial': '#28a745',
            'video': '#dc3545',
            'book': '#6f42c1'
        }
        color = colors.get(obj.resource_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_resource_type_display()
        )
    get_type_badge.short_description = 'Type'
    
    def get_difficulty_badge(self, obj):
        """Display difficulty as badge"""
        colors = {
            'beginner': '#28a745',
            'intermediate': '#ffc107',
            'advanced': '#dc3545'
        }
        color = colors.get(obj.difficulty_level, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_difficulty_level_display()
        )
    get_difficulty_badge.short_description = 'Level'
    
    def featured_badge(self, obj):
        """Display featured status"""
        if obj.featured:
            return format_html('<span style="color: #ffc107;">⭐ Featured</span>')
        return '—'
    featured_badge.short_description = 'Featured'
    
    def get_engagement_display(self, obj):
        """Display views and likes"""
        return format_html(
            '👁️ {} | 👍 {}',
            obj.views_count, obj.likes_count
        )
    get_engagement_display.short_description = 'Engagement'
    
    def get_thumbnail(self, obj):
        """Display thumbnail"""
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 5px;" />',
                obj.thumbnail.url
            )
        return '—'
    get_thumbnail.short_description = 'Thumbnail'


@admin.register(UserResourceProgress)
class UserResourceProgressAdmin(admin.ModelAdmin):
    """Admin interface for User Resource Progress"""
    list_display = (
        'user_link',
        'resource_link',
        'get_progress_display',
        'completion_badge',
        'started_at'
    )
    list_filter = ('is_completed', 'is_liked', 'started_at', 'completed_at')
    search_fields = ('user__username', 'resource__title')
    readonly_fields = ('user', 'resource', 'started_at', 'completed_at')
    ordering = ('-started_at',)
    
    fieldsets = (
        ('User & Resource', {
            'fields': ('user', 'resource')
        }),
        ('Progress', {
            'fields': ('progress_percentage', 'is_completed', 'is_liked')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def resource_link(self, obj):
        """Display resource with link"""
        url = reverse('admin:resource_hub_resource_change', args=[obj.resource.id])
        return format_html('<a href="{}">{}</a>', url, obj.resource.title[:40])
    resource_link.short_description = 'Resource'
    
    def get_progress_display(self, obj):
        """Display progress bar"""
        progress = obj.progress_percentage
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background-color: #0c5460; height: 20px; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">{}</div>'
            '</div>%',
            min(progress, 100), progress
        )
    get_progress_display.short_description = 'Progress'
    
    def completion_badge(self, obj):
        """Display completion status"""
        if obj.is_completed:
            return format_html('<span style="color: #28a745;">✅ Completed</span>')
        return '⏳ In Progress'
    completion_badge.short_description = 'Status'


@admin.register(SkillPath)
class SkillPathAdmin(admin.ModelAdmin):
    """Admin interface for Skill Paths"""
    list_display = (
        'name',
        'target_skill',
        'get_difficulty_badge',
        'get_resources_count',
        'estimated_hours'
    )
    list_filter = ('difficulty_level', 'created_at')
    search_fields = ('name', 'target_skill', 'description')
    readonly_fields = ('created_at',)
    ordering = ('target_skill',)
    filter_horizontal = ('resources',)
    
    fieldsets = (
        ('Skill Path Info', {
            'fields': ('name', 'target_skill', 'description')
        }),
        ('Curriculum', {
            'fields': ('resources',)
        }),
        ('Details', {
            'fields': ('difficulty_level', 'estimated_hours')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_difficulty_badge(self, obj):
        """Display difficulty as badge"""
        colors = {
            'beginner': '#28a745',
            'intermediate': '#ffc107',
            'advanced': '#dc3545'
        }
        color = colors.get(obj.difficulty_level, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_difficulty_level_display()
        )
    get_difficulty_badge.short_description = 'Level'
    
    def get_resources_count(self, obj):
        """Display resource count"""
        count = obj.resources.count()
        return format_html('<strong>{}</strong> resources', count)
    get_resources_count.short_description = 'Resources'