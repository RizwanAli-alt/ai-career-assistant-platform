from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    ForumCategory, ForumThread, ForumReply, ForumUpvote,
    UserBadge, UserReputation
)


class ForumThreadInline(admin.TabularInline):
    """Inline threads for ForumCategory"""
    model = ForumThread
    extra = 0
    fields = ('title', 'author', 'status', 'views_count', 'created_at')
    readonly_fields = ('author', 'created_at', 'views_count')
    can_delete = False


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    """Admin interface for Forum Categories"""
    list_display = ('name', 'get_threads_count', 'order')
    list_filter = ('order',)
    search_fields = ('name', 'description')
    ordering = ('order',)
    inlines = [ForumThreadInline]
    
    fieldsets = (
        ('Category Info', {
            'fields': ('name', 'description', 'icon', 'color', 'order')
        }),
    )
    
    def get_threads_count(self, obj):
        """Display thread count"""
        count = obj.threads.count()
        open_count = obj.threads.filter(status='open').count()
        return format_html(
            '<strong>{}</strong> threads ({} open)',
            count, open_count
        )
    get_threads_count.short_description = 'Threads'


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    """Admin interface for Forum Threads"""
    list_display = (
        'title_preview',
        'author_link',
        'category',
        'get_status_badge',
        'get_engagement_display',
        'created_at'
    )
    list_filter = ('status', 'category', 'is_featured', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('created_at', 'updated_at', 'views_count', 'replies_count')
    ordering = ('-is_featured', '-updated_at')
    
    fieldsets = (
        ('Thread Info', {
            'fields': ('title', 'category', 'author', 'status')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Engagement', {
            'fields': (
                'is_featured',
                'views_count',
                'replies_count'
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
    
    def author_link(self, obj):
        """Display author with link"""
        url = reverse('admin:auth_user_change', args=[obj.author.id])
        return format_html('<a href="{}">{}</a>', url, obj.author.username)
    author_link.short_description = 'Author'
    
    def get_status_badge(self, obj):
        """Display status as badge"""
        colors = {
            'open': '#28a745',
            'closed': '#dc3545',
            'pinned': '#ffc107',
            'locked': '#6c757d'
        }
        color = colors.get(obj.status, '#0c5460')
        status = '📌 Pinned' if obj.status == 'pinned' else obj.get_status_display()
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, status
        )
    get_status_badge.short_description = 'Status'
    
    def get_engagement_display(self, obj):
        """Display views and replies"""
        return format_html(
            '👁️ {} | 💬 {}',
            obj.views_count, obj.replies_count
        )
    get_engagement_display.short_description = 'Engagement'


class ForumReplyInline(admin.TabularInline):
    """Inline replies for ForumThread"""
    model = ForumReply
    extra = 0
    fields = ('author', 'content_preview', 'is_solution', 'upvotes')
    readonly_fields = ('author', 'content_preview', 'upvotes')
    can_delete = False
    
    def content_preview(self, obj):
        """Display content preview"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    """Admin interface for Forum Replies"""
    list_display = (
        'thread_link',
        'author_link',
        'solution_badge',
        'get_upvotes_display',
        'created_at'
    )
    list_filter = ('is_solution', 'created_at')
    search_fields = ('content', 'author__username', 'thread__title')
    readonly_fields = ('thread', 'author', 'created_at', 'updated_at', 'upvotes')
    ordering = ('-is_solution', '-upvotes')
    
    fieldsets = (
        ('Reply Info', {
            'fields': ('thread', 'author', 'is_solution')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Engagement', {
            'fields': ('upvotes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def thread_link(self, obj):
        """Display thread with link"""
        url = reverse('admin:forum_forumthread_change', args=[obj.thread.id])
        return format_html('<a href="{}">{}</a>', url, obj.thread.title[:40])
    thread_link.short_description = 'Thread'
    
    def author_link(self, obj):
        """Display author with link"""
        url = reverse('admin:auth_user_change', args=[obj.author.id])
        return format_html('<a href="{}">{}</a>', url, obj.author.username)
    author_link.short_description = 'Author'
    
    def solution_badge(self, obj):
        """Display solution status"""
        if obj.is_solution:
            return format_html('<span style="color: #28a745;">✅ Solution</span>')
        return '—'
    solution_badge.short_description = 'Solution'
    
    def get_upvotes_display(self, obj):
        """Display upvotes"""
        return format_html('👍 <strong>{}</strong>', obj.upvotes)
    get_upvotes_display.short_description = 'Upvotes'


@admin.register(ForumUpvote)
class ForumUpvoteAdmin(admin.ModelAdmin):
    """Admin interface for Forum Upvotes"""
    list_display = ('user_link', 'reply_link', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'reply__content')
    readonly_fields = ('user', 'reply', 'created_at')
    ordering = ('-created_at',)
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def reply_link(self, obj):
        """Display reply with link"""
        url = reverse('admin:forum_forumreply_change', args=[obj.reply.id])
        preview = obj.reply.content[:30] + '...'
        return format_html('<a href="{}">{}</a>', url, preview)
    reply_link.short_description = 'Reply'


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    """Admin interface for User Badges"""
    list_display = (
        'user_link',
        'get_badge_type_display',
        'earned_at'
    )
    list_filter = ('badge_type', 'earned_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('user', 'earned_at')
    ordering = ('-earned_at',)
    
    fieldsets = (
        ('Badge Info', {
            'fields': ('user', 'badge_type')
        }),
        ('Details', {
            'fields': ('description', 'icon')
        }),
        ('Timestamp', {
            'fields': ('earned_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'


@admin.register(UserReputation)
class UserReputationAdmin(admin.ModelAdmin):
    """Admin interface for User Reputation"""
    list_display = (
        'user_link',
        'get_reputation_display',
        'threads_created',
        'helpful_replies'
    )
    list_filter = ('reputation_points',)
    search_fields = ('user__username',)
    readonly_fields = ('user',)
    ordering = ('-reputation_points',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Reputation', {
            'fields': (
                'reputation_points',
                'threads_created',
                'helpful_replies'
            )
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_reputation_display(self, obj):
        """Display reputation points with color"""
        points = obj.reputation_points
        if points >= 500:
            color = '#ffc107'
            badge = '👑 Expert'
        elif points >= 200:
            color = '#0b7dda'
            badge = '🌟 Contributor'
        else:
            color = '#6c757d'
            badge = '👤 Member'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ({})</span>',
            color, badge, points
        )
    get_reputation_display.short_description = 'Reputation'