from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    UserProfile, Category, Post, Reply,
    Like, Badge, UserBadge, MentorshipRequest, Notification
)


# ─────────────────────────────────────────────
#  INLINE: UserProfile inside User admin
# ─────────────────────────────────────────────
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ("role", "bio", "avatar", "points", "linkedin_url", "github_url", "is_warned")
    readonly_fields = ("points",)


# ─────────────────────────────────────────────
#  CUSTOM MODERATION ACTIONS
# ─────────────────────────────────────────────

@admin.action(description="🚫 Hide selected posts (soft delete)")
def hide_posts(modeladmin, request, queryset):
    updated = queryset.update(is_hidden=True)
    modeladmin.message_user(request, f"{updated} post(s) hidden.", messages.WARNING)


@admin.action(description="🚩 Flag selected posts for review")
def flag_posts(modeladmin, request, queryset):
    updated = queryset.update(is_flagged=True)
    modeladmin.message_user(request, f"{updated} post(s) flagged.", messages.WARNING)


@admin.action(description="✅ Unhide selected posts")
def unhide_posts(modeladmin, request, queryset):
    updated = queryset.update(is_hidden=False, is_flagged=False)
    modeladmin.message_user(request, f"{updated} post(s) restored.", messages.SUCCESS)


@admin.action(description="⚠️ Warn authors of selected posts")
def warn_post_authors(modeladmin, request, queryset):
    warned = 0
    for post in queryset.select_related("author__userprofile"):
        try:
            post.author.userprofile.is_warned = True
            post.author.userprofile.save()
            warned += 1
        except UserProfile.DoesNotExist:
            pass
    modeladmin.message_user(request, f"{warned} user(s) warned.", messages.WARNING)


@admin.action(description="🚫 Hide selected replies")
def hide_replies(modeladmin, request, queryset):
    updated = queryset.update(is_hidden=True)
    modeladmin.message_user(request, f"{updated} reply(ies) hidden.", messages.WARNING)


@admin.action(description="🚩 Flag selected replies")
def flag_replies(modeladmin, request, queryset):
    updated = queryset.update(is_flagged=True)
    modeladmin.message_user(request, f"{updated} reply(ies) flagged.", messages.WARNING)


# ─────────────────────────────────────────────
#  UserProfile ADMIN
# ─────────────────────────────────────────────
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "points", "is_warned", "colored_role")
    list_filter = ("role", "is_warned")
    search_fields = ("user__username", "user__email", "bio")
    readonly_fields = ("points",)
    ordering = ("-points",)

    def colored_role(self, obj):
        color_map = {
            "student": "#3B82F6",
            "senior": "#7C3AED",
            "employer": "#10B981",
            "mentor": "#F59E0B",
        }
        color = color_map.get(obj.role, "#999")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_role_display(),
        )
    colored_role.short_description = "Role (colored)"


# ─────────────────────────────────────────────
#  Category ADMIN
# ─────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


# ─────────────────────────────────────────────
#  Post ADMIN
# ─────────────────────────────────────────────
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title", "author", "category", "is_pinned",
        "is_hidden", "is_flagged", "views",
        "like_count", "reply_count", "created_at",
    )
    list_filter = ("is_hidden", "is_flagged", "is_pinned", "category")
    search_fields = ("title", "body", "author__username")
    readonly_fields = ("views", "created_at", "updated_at")
    ordering = ("-created_at",)
    actions = [hide_posts, unhide_posts, flag_posts, warn_post_authors]

    fieldsets = (
        ("Content", {
            "fields": ("author", "category", "title", "body")
        }),
        ("Moderation", {
            "fields": ("is_pinned", "is_hidden", "is_flagged")
        }),
        ("Stats (read-only)", {
            "fields": ("views", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def like_count(self, obj):
        return obj.like_count()
    like_count.short_description = "Likes"

    def reply_count(self, obj):
        return obj.reply_count()
    reply_count.short_description = "Replies"


# ─────────────────────────────────────────────
#  Reply ADMIN
# ─────────────────────────────────────────────
@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("short_body", "author", "post", "parent", "is_hidden", "is_flagged", "created_at")
    list_filter = ("is_hidden", "is_flagged")
    search_fields = ("body", "author__username", "post__title")
    readonly_fields = ("created_at",)
    actions = [hide_replies, flag_replies]

    def short_body(self, obj):
        return obj.body[:60] + "..." if len(obj.body) > 60 else obj.body
    short_body.short_description = "Reply (preview)"


# ─────────────────────────────────────────────
#  Like ADMIN
# ─────────────────────────────────────────────
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "reply", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user__username",)
    readonly_fields = ("created_at",)


# ─────────────────────────────────────────────
#  Badge ADMIN
# ─────────────────────────────────────────────
@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "points_required")
    ordering = ("points_required",)


# ─────────────────────────────────────────────
#  UserBadge ADMIN
# ─────────────────────────────────────────────
@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    search_fields = ('user__username', 'badge__name')
    readonly_fields = ('earned_at',)


# ─────────────────────────────────────────────
#  MentorshipRequest ADMIN
# ─────────────────────────────────────────────
@admin.register(MentorshipRequest)
class MentorshipRequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__username", "to_user__username")
    readonly_fields = ("created_at",)


# ─────────────────────────────────────────────
#  Notification ADMIN
# ─────────────────────────────────────────────
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "short_message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "message")
    readonly_fields = ("created_at",)

    def short_message(self, obj):
        return obj.message[:70] + "..." if len(obj.message) > 70 else obj.message
    short_message.short_description = "Message"