from django.contrib import admin
from django.utils.html import format_html
from .models import Resource, Bookmark, UserProgress, CVSkillGap


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'platform', 'category', 'level', 'resource_type', 'is_free', 'view_count', 'created_at')
    list_filter = ('category', 'level', 'resource_type', 'is_free', 'platform')
    search_fields = ('title', 'description', 'tags')
    readonly_fields = ('view_count', 'created_at')
    ordering = ('-view_count', '-created_at')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'resource', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'resource__title')


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'resource', 'status', 'completed_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'resource__title')


@admin.register(CVSkillGap)
class CVSkillGapAdmin(admin.ModelAdmin):
    list_display = ('user', 'skill_name', 'created_at')
    search_fields = ('user__username', 'skill_name')