from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    InterviewSession, InterviewQuestion, InterviewAnswer,
    InterviewTemplate, InterviewFeedback
)


class InterviewQuestionInline(admin.TabularInline):
    """Inline questions for InterviewSession"""
    model = InterviewQuestion
    extra = 0
    fields = ('order', 'question_text', 'difficulty', 'category')
    readonly_fields = ('order',)
    can_delete = False


class InterviewAnswerInline(admin.TabularInline):
    """Inline answers for InterviewSession"""
    model = InterviewAnswer
    extra = 0
    fields = ('question', 'score', 'duration_seconds', 'is_answered')
    readonly_fields = ('question', 'score', 'duration_seconds')
    can_delete = False


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    """Admin interface for Interview Sessions"""
    list_display = (
        'user_link',
        'title',
        'get_type_badge',
        'get_status_badge',
        'get_score_display',
        'duration_minutes',
        'created_at'
    )
    list_filter = (
        'interview_type',
        'status',
        'created_at',
    )
    search_fields = ('user__username', 'title', 'job_role')
    readonly_fields = (
        'user',
        'created_at',
        'started_at',
        'completed_at',
        'duration_minutes',
        'overall_score'
    )
    ordering = ('-created_at',)
    inlines = [InterviewQuestionInline]
    
    fieldsets = (
        ('Session Info', {
            'fields': ('user', 'title', 'interview_type', 'job_role')
        }),
        ('Progress', {
            'fields': ('status', 'overall_score', 'duration_minutes')
        }),
        ('Dates', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def get_type_badge(self, obj):
        """Display interview type as badge"""
        colors = {
            'technical': '#0c5460',
            'behavioral': '#0b7dda',
            'mixed': '#6f42c1'
        }
        color = colors.get(obj.interview_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_interview_type_display()
        )
    get_type_badge.short_description = 'Type'
    
    def get_status_badge(self, obj):
        """Display status badge"""
        colors = {
            'not_started': '#6c757d',
            'in_progress': '#ffc107',
            'completed': '#28a745'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    get_status_badge.short_description = 'Status'
    
    def get_score_display(self, obj):
        """Display score with color"""
        score = obj.overall_score
        if score >= 80:
            color = '#28a745'
        elif score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}/100</span>',
            color, score
        )
    get_score_display.short_description = 'Score'


@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    """Admin interface for Interview Questions"""
    list_display = (
        'session_link',
        'question_preview',
        'get_difficulty_badge',
        'category',
        'order'
    )
    list_filter = ('difficulty', 'category', 'session__interview_type')
    search_fields = ('question_text', 'category', 'session__title')
    readonly_fields = ('session', 'order')
    ordering = ('session', 'order')
    
    fieldsets = (
        ('Question Info', {
            'fields': ('session', 'order')
        }),
        ('Content', {
            'fields': ('question_text', 'difficulty', 'category')
        }),
    )
    
    def session_link(self, obj):
        """Display session with link"""
        url = reverse('admin:ai_interview_interviewsession_change', args=[obj.session.id])
        return format_html('<a href="{}">{}</a>', url, obj.session.title)
    session_link.short_description = 'Session'
    
    def question_preview(self, obj):
        """Display question preview"""
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question'
    
    def get_difficulty_badge(self, obj):
        """Display difficulty badge"""
        colors = {
            'easy': '#28a745',
            'medium': '#ffc107',
            'hard': '#dc3545'
        }
        color = colors.get(obj.difficulty, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_difficulty_display()
        )
    get_difficulty_badge.short_description = 'Difficulty'


@admin.register(InterviewAnswer)
class InterviewAnswerAdmin(admin.ModelAdmin):
    """Admin interface for Interview Answers"""
    list_display = (
        'question_link',
        'get_score_display',
        'duration_display',
        'is_answered_badge',
        'recorded_at'
    )
    list_filter = ('is_answered', 'recorded_at')  # ✅ FIXED: Removed NumericRangeFilter
    search_fields = ('answer_text', 'feedback', 'question__question_text')
    readonly_fields = ('question', 'recorded_at')
    ordering = ('-recorded_at',)
    
    fieldsets = (
        ('Answer Info', {
            'fields': ('question', 'is_answered')
        }),
        ('Answer & Feedback', {
            'fields': ('answer_text', 'feedback')
        }),
        ('Scoring', {
            'fields': ('score', 'duration_seconds')
        }),
        ('Timestamp', {
            'fields': ('recorded_at',),
            'classes': ('collapse',)
        }),
    )
    
    def question_link(self, obj):
        """Display question with link"""
        url = reverse('admin:ai_interview_interviewquestion_change', args=[obj.question.id])
        preview = obj.question.question_text[:30] + '...'
        return format_html('<a href="{}">{}</a>', url, preview)
    question_link.short_description = 'Question'
    
    def get_score_display(self, obj):
        """Display score with color"""
        score = obj.score
        if score >= 80:
            color = '#28a745'
        elif score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}</span>',
            color, score
        )
    get_score_display.short_description = 'Score'
    
    def duration_display(self, obj):
        """Display duration"""
        minutes = obj.duration_seconds // 60
        seconds = obj.duration_seconds % 60
        return f'{minutes}m {seconds}s'
    duration_display.short_description = 'Duration'
    
    def is_answered_badge(self, obj):
        """Display answered status"""
        if obj.is_answered:
            return format_html('<span style="color: #28a745;">✅ Answered</span>')
        return format_html('<span style="color: #dc3545;">❌ Skipped</span>')
    is_answered_badge.short_description = 'Status'


@admin.register(InterviewTemplate)
class InterviewTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Interview Templates"""
    list_display = (
        'name',
        'interview_type',
        'active_badge',
        'created_at'
    )
    list_filter = ('is_active', 'interview_type', 'created_at')
    search_fields = ('name', 'description', 'job_roles')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Template Info', {
            'fields': ('name', 'description', 'interview_type')
        }),
        ('Jobs', {
            'fields': ('job_roles',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def active_badge(self, obj):
        """Display active status"""
        color = '#28a745' if obj.is_active else '#dc3545'
        status = '✅ Active' if obj.is_active else '❌ Inactive'
        return format_html('<span style="color: {};">{}</span>', color, status)
    active_badge.short_description = 'Status'


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for Interview Feedback"""
    list_display = (
        'session_link',
        'get_overall_score_display',
        'communication_score',
        'technical_score',
        'problem_solving_score'
    )
    list_filter = ('created_at',)
    search_fields = ('session__user__username', 'strengths', 'improvements')
    readonly_fields = ('session', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Session', {
            'fields': ('session',)
        }),
        ('Scores', {
            'fields': (
                'communication_score',
                'technical_score',
                'problem_solving_score'
            )
        }),
        ('Feedback', {
            'fields': (
                'strengths',
                'improvements',
                'overall_feedback'
            )
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def session_link(self, obj):
        """Display session with link"""
        url = reverse('admin:ai_interview_interviewsession_change', args=[obj.session.id])
        return format_html('<a href="{}">{}</a>', url, obj.session.title)
    session_link.short_description = 'Session'
    
    def get_overall_score_display(self, obj):
        """Display overall score"""
        avg_score = (obj.communication_score + obj.technical_score + obj.problem_solving_score) / 3
        if avg_score >= 80:
            color = '#28a745'
        elif avg_score >= 60:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}</span>',
            color, avg_score
        )
    get_overall_score_display.short_description = 'Average Score'