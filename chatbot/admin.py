from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import ChatSession, ChatMessage, FAQCategory, FAQ, CareerTip, UserFeedback


class ChatMessageInline(admin.TabularInline):
    """Inline chat messages for ChatSession"""
    model = ChatMessage
    extra = 0
    fields = ('message_type', 'content', 'confidence_score', 'intent', 'timestamp')
    readonly_fields = ('message_type', 'content', 'confidence_score', 'intent', 'timestamp')
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """Admin interface for Chat Sessions"""
    list_display = (
        'user_link',
        'title',
        'get_message_count',
        'is_active_badge',
        'updated_at',
        'created_at'
    )
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('user__username', 'title')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-updated_at',)
    inlines = [ChatMessageInline]
    
    fieldsets = (
        ('Session Info', {
            'fields': ('user', 'title', 'is_active')
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
    
    def get_message_count(self, obj):
        """Display count of messages"""
        count = obj.messages.count()
        return format_html('<strong>{}</strong> messages', count)
    get_message_count.short_description = 'Messages'
    
    def is_active_badge(self, obj):
        """Display active status"""
        color = '#28a745' if obj.is_active else '#dc3545'
        status = '✅ Active' if obj.is_active else '❌ Inactive'
        return format_html('<span style="color: {};">{}</span>', color, status)
    is_active_badge.short_description = 'Status'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for Chat Messages"""
    list_display = (
        'session_link',
        'get_message_type_icon',
        'content_preview',
        'get_confidence_display',
        'intent',
        'timestamp'
    )
    list_filter = ('message_type', 'timestamp')  # ✅ FIXED: Removed NumericRangeFilter
    search_fields = ('session__user__username', 'content', 'intent')
    readonly_fields = ('session', 'timestamp')
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Message Info', {
            'fields': ('session', 'message_type')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Bot Analysis', {
            'fields': ('confidence_score', 'intent'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def session_link(self, obj):
        """Display session with link"""
        url = reverse('admin:chatbot_chatsession_change', args=[obj.session.id])
        return format_html('<a href="{}">{}</a>', url, obj.session.title)
    session_link.short_description = 'Session'
    
    def get_message_type_icon(self, obj):
        """Display message type with icon"""
        icons = {'user': '👤 User', 'bot': '🤖 Bot'}
        return icons.get(obj.message_type, obj.get_message_type_display())
    get_message_type_icon.short_description = 'Type'
    
    def content_preview(self, obj):
        """Display message preview"""
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    content_preview.short_description = 'Content'
    
    def get_confidence_display(self, obj):
        """Display confidence score with color"""
        score = obj.confidence_score
        if score >= 0.8:
            color = '#28a745'
        elif score >= 0.6:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2%}</span>',
            color, score
        )
    get_confidence_display.short_description = 'Confidence'


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    """Admin interface for FAQ Categories"""
    list_display = ('name', 'get_faq_count', 'order')
    list_filter = ('order',)
    search_fields = ('name', 'description')
    ordering = ('order',)
    
    fieldsets = (
        ('Category Info', {
            'fields': ('name', 'description', 'icon', 'order')
        }),
    )
    
    def get_faq_count(self, obj):
        """Display count of FAQs"""
        count = obj.faqs.count()
        active = obj.faqs.filter(is_active=True).count()
        return format_html(
            '<strong>{}</strong> FAQs ({} active)',
            count, active
        )
    get_faq_count.short_description = 'FAQs'


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """Admin interface for FAQs"""
    list_display = (
        'question_preview',
        'category',
        'is_active_badge',
        'get_views_display',
        'created_at'
    )
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('question', 'answer', 'keywords')
    readonly_fields = ('created_at', 'views_count')
    ordering = ('-views_count',)
    
    fieldsets = (
        ('Question & Answer', {
            'fields': ('category', 'question', 'answer')
        }),
        ('SEO & Keywords', {
            'fields': ('keywords',)
        }),
        ('Engagement', {
            'fields': ('is_active', 'views_count'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def question_preview(self, obj):
        """Display question preview"""
        return obj.question[:60] + '...' if len(obj.question) > 60 else obj.question
    question_preview.short_description = 'Question'
    
    def is_active_badge(self, obj):
        """Display active status"""
        color = '#28a745' if obj.is_active else '#dc3545'
        status = '✅ Active' if obj.is_active else '❌ Inactive'
        return format_html('<span style="color: {};">{}</span>', color, status)
    is_active_badge.short_description = 'Status'
    
    def get_views_display(self, obj):
        """Display views with icon"""
        return format_html('👁️ <strong>{}</strong>', obj.views_count)
    get_views_display.short_description = 'Views'


@admin.register(CareerTip)
class CareerTipAdmin(admin.ModelAdmin):
    """Admin interface for Career Tips"""
    list_display = (
        'title',
        'get_category_badge',
        'featured_badge',
        'get_views_display',
        'created_at'
    )
    list_filter = ('category', 'featured', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'views_count', 'get_thumbnail')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'content', 'category')
        }),
        ('Media', {
            'fields': ('image', 'get_thumbnail')
        }),
        ('Status', {
            'fields': ('featured',)
        }),
        ('Engagement', {
            'fields': ('views_count',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_category_badge(self, obj):
        """Display category as badge"""
        colors = {
            'resume': '#0c5460',
            'interview': '#28a745',
            'salary': '#ffc107',
            'skills': '#fd7e14',
            'networking': '#0b7dda',
            'job_search': '#6f42c1',
            'career_change': '#e83e8c'
        }
        color = colors.get(obj.category, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_category_display()
        )
    get_category_badge.short_description = 'Category'
    
    def featured_badge(self, obj):
        """Display featured status"""
        if obj.featured:
            return format_html('<span style="color: #ffc107;">⭐ Featured</span>')
        return '—'
    featured_badge.short_description = 'Featured'
    
    def get_views_display(self, obj):
        """Display views"""
        return format_html('👁️ <strong>{}</strong>', obj.views_count)
    get_views_display.short_description = 'Views'
    
    def get_thumbnail(self, obj):
        """Display image thumbnail"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 5px;" />',
                obj.image.url
            )
        return '—'
    get_thumbnail.short_description = 'Thumbnail'


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for User Feedback"""
    list_display = (
        'user_link',
        'get_rating_badge',
        'message_link',
        'created_at'
    )
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'comment', 'message__content')
    readonly_fields = ('user', 'message', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Feedback Info', {
            'fields': ('user', 'message', 'rating')
        }),
        ('Comment', {
            'fields': ('comment',)
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
    
    def message_link(self, obj):
        """Display message with link"""
        url = reverse('admin:chatbot_chatmessage_change', args=[obj.message.id])
        preview = obj.message.content[:30] + '...'
        return format_html('<a href="{}">{}</a>', url, preview)
    message_link.short_description = 'Message'
    
    def get_rating_badge(self, obj):
        """Display rating as badge"""
        colors = {1: '#dc3545', 2: '#fd7e14', 3: '#ffc107', 4: '#0b7dda', 5: '#28a745'}
        color = colors.get(obj.rating, '#6c757d')
        stars = '⭐' * obj.rating
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ({})</span>',
            color, stars, obj.get_rating_display()
        )
    get_rating_badge.short_description = 'Rating'