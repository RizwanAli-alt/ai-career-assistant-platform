from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q, Avg
import json
from .models import CVAnalysis, CVFeedback, CVTemplate, KeywordDatabase


class CVFeedbackInline(admin.TabularInline):
    """Inline feedback display for CVAnalysis"""
    model = CVFeedback
    extra = 0
    fields = ('feedback_type', 'section', 'severity', 'issue', 'suggestion')
    readonly_fields = ('feedback_type', 'section', 'severity', 'issue', 'suggestion')
    can_delete = False


@admin.register(CVAnalysis)
class CVAnalysisAdmin(admin.ModelAdmin):
    """Admin interface for CV Analysis"""
    list_display = (
        'user_link',
        'get_score_display',
        'get_score_rating',
        'is_analyzed',
        'created_at',
        'analysis_time_taken',
        'get_file_link'
    )
    list_filter = (
        'is_analyzed',
        'created_at',
    )
    search_fields = ('user__username', 'user__email', 'cv_file')
    readonly_fields = (
        'user',
        'created_at',
        'updated_at',
        'is_analyzed',
        'analysis_time_taken',
        'get_extracted_skills_display',
        'get_feedback_summary'
    )
    ordering = ('-created_at',)
    inlines = [CVFeedbackInline]
    
    fieldsets = (
        ('User & File', {
            'fields': ('user', 'cv_file', 'get_file_link')
        }),
        ('Overall Score', {
            'fields': ('overall_score', 'is_analyzed', 'analysis_time_taken')
        }),
        ('Score Breakdown', {
            'fields': (
                'format_score',
                'content_score',
                'keyword_score',
                'readability_score'
            )
        }),
        ('Feedback & Analysis', {
            'fields': (
                'format_feedback',
                'content_feedback',
                'keyword_feedback',
                'readability_feedback',
                'overall_feedback',
                'get_feedback_summary'
            ),
            'classes': ('collapse',)
        }),
        ('Extracted Data', {
            'fields': (
                'extracted_skills',
                'extracted_experience',
                'extracted_education',
                'get_extracted_skills_display'
            ),
            'classes': ('collapse',)
        }),
        ('Recommendations', {
            'fields': ('recommendations',),
            'classes': ('collapse',)
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
    
    def get_score_display(self, obj):
        """Display score with color gradient"""
        score = obj.overall_score
        if score >= 90:
            color = '#28a745'
            bg = '#d4edda'
        elif score >= 75:
            color = '#0c5460'
            bg = '#d1ecf1'
        elif score >= 60:
            color = '#856404'
            bg = '#fff3cd'
        else:
            color = '#721c24'
            bg = '#f8d7da'
        
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 5px 10px; border-radius: 3px; font-weight: bold;">{}/100</span>',
            bg, color, score
        )
    get_score_display.short_description = 'Score'
    
    def get_score_rating(self, obj):
        """Display score rating"""
        rating = obj.get_score_rating()
        ratings = {
            'excellent': ('🟢 Excellent', '#28a745'),
            'good': ('🔵 Good', '#0c5460'),
            'average': ('🟡 Average', '#856404'),
            'poor': ('🔴 Poor', '#721c24')
        }
        label, color = ratings.get(rating, ('Unknown', '#6c757d'))
        return format_html('<span style="color: {};">{}</span>', color, label)
    get_score_rating.short_description = 'Rating'
    
    def get_file_link(self, obj):
        """Display download link for CV file"""
        if obj.cv_file:
            return format_html(
                '<a href="{}" target="_blank">📄 Download CV</a>',
                obj.cv_file.url
            )
        return '—'
    get_file_link.short_description = 'CV File'
    
    def get_extracted_skills_display(self, obj):
        """Display extracted skills in formatted way"""
        if obj.extracted_skills:
            try:
                skills = json.loads(obj.extracted_skills)
                technical = ', '.join(skills.get('technical', [])[:10])
                soft = ', '.join(skills.get('soft', [])[:5])
                html = f'<strong>Technical:</strong> {technical}<br><strong>Soft:</strong> {soft}'
                return format_html(html)
            except (json.JSONDecodeError, TypeError):
                return '—'
        return '—'
    get_extracted_skills_display.short_description = 'Extracted Skills'
    
    def get_feedback_summary(self, obj):
        """Display summary of feedback"""
        feedbacks = obj.feedback_items.all()
        if feedbacks.exists():
            critical = feedbacks.filter(severity='critical').count()
            major = feedbacks.filter(severity='major').count()
            minor = feedbacks.filter(severity='minor').count()
            
            html = f'<strong>Critical:</strong> {critical} | <strong>Major:</strong> {major} | <strong>Minor:</strong> {minor}'
            return format_html(html)
        return '—'
    get_feedback_summary.short_description = 'Feedback Summary'


@admin.register(CVFeedback)
class CVFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for CV Feedback"""
    list_display = (
        'analysis_link',
        'get_feedback_type_display',
        'section',
        'get_severity_badge',
        'created_at'
    )
    list_filter = ('feedback_type', 'severity', 'section', 'created_at')
    search_fields = ('analysis__user__username', 'section', 'issue', 'suggestion')
    readonly_fields = ('analysis', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Analysis & Type', {
            'fields': ('analysis', 'feedback_type')
        }),
        ('Details', {
            'fields': ('section', 'severity')
        }),
        ('Content', {
            'fields': ('issue', 'suggestion')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def analysis_link(self, obj):
        """Display link to analysis"""
        url = reverse('admin:cv_analyzer_cvanalysis_change', args=[obj.analysis.id])
        user = obj.analysis.user.username
        return format_html(
            '<a href="{}">{} ({})</a>',
            url, obj.analysis.user.username, obj.analysis.created_at.strftime('%Y-%m-%d')
        )
    analysis_link.short_description = 'Analysis'
    
    def get_feedback_type_display(self, obj):
        """Display feedback type with emoji"""
        emojis = {
            'spelling': '🔤 Spelling',
            'grammar': '✏️ Grammar',
            'format': '📋 Format',
            'content': '📝 Content',
            'suggestion': '💡 Suggestion'
        }
        return emojis.get(obj.feedback_type, obj.get_feedback_type_display())
    get_feedback_type_display.short_description = 'Type'
    
    def get_severity_badge(self, obj):
        """Display severity as badge"""
        colors = {
            'critical': '#dc3545',
            'major': '#fd7e14',
            'minor': '#ffc107'
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_severity_display()
        )
    get_severity_badge.short_description = 'Severity'


@admin.register(CVTemplate)
class CVTemplateAdmin(admin.ModelAdmin):
    """Admin interface for CV Templates"""
    list_display = (
        'name',
        'category',
        'is_active',
        'get_preview_thumbnail',
        'created_at'
    )
    list_filter = ('is_active', 'category', 'created_at')
    search_fields = ('name', 'category', 'description')
    ordering = ('category', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'description')
        }),
        ('Files', {
            'fields': ('template_file', 'preview_image', 'get_preview_thumbnail')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'get_preview_thumbnail')
    
    def get_preview_thumbnail(self, obj):
        """Display preview image thumbnail"""
        if obj.preview_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 5px;" />',
                obj.preview_image.url
            )
        return '—'
    get_preview_thumbnail.short_description = 'Preview'


@admin.register(KeywordDatabase)
class KeywordDatabaseAdmin(admin.ModelAdmin):
    """Admin interface for Keyword Database"""
    list_display = ('industry', 'job_title', 'get_keywords_count', 'created_at')
    list_filter = ('industry', 'created_at')
    search_fields = ('industry', 'job_title', 'keywords')
    ordering = ('industry', 'job_title')
    
    fieldsets = (
        ('Classification', {
            'fields': ('industry', 'job_title')
        }),
        ('Keywords', {
            'fields': ('keywords', 'get_keywords_preview')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'get_keywords_preview')
    
    def get_keywords_count(self, obj):
        """Display count of keywords"""
        count = len(obj.get_keywords_list())
        return format_html('<strong>{}</strong> keywords', count)
    get_keywords_count.short_description = 'Keywords'
    
    def get_keywords_preview(self, obj):
        """Display first 10 keywords as preview"""
        keywords = obj.get_keywords_list()[:10]
        html = ' '.join([f'<span style="background-color: #e9ecef; padding: 3px 8px; border-radius: 3px; margin-right: 5px;">{kw}</span>' for kw in keywords])
        if len(obj.get_keywords_list()) > 10:
            html += f'<br><em>... and {len(obj.get_keywords_list()) - 10} more</em>'
        return format_html(html)
    get_keywords_preview.short_description = 'Keywords Preview'