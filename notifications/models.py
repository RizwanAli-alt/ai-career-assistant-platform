from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    """User notifications"""

    NOTIFICATION_TYPE = [
        ("job_match", "Job Match"),
        ("application_update", "Application Update"),
        ("forum_reply", "Forum Reply"),
        ("message", "Message"),
        ("alert", "Alert"),
        ("achievement", "Achievement"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE
    )

    title = models.CharField(max_length=200)
    message = models.TextField()
    icon = models.CharField(max_length=50, default="fa-bell")

    # Link to related object (used by frontend templates)
    related_url = models.URLField(blank=True, null=True)

    # ✅ Extra flexible data (job_id, score, ids, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    # ✅ Prevent duplicate notifications (optional use)
    dedupe_key = models.CharField(max_length=128, blank=True, null=True)

    # Status fields
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [
            # Main notification list query
            models.Index(fields=["user", "is_archived", "-created_at"]),

            # Unread count filtering
            models.Index(fields=["user", "is_archived", "is_read"]),

            # Duplicate prevention lookup
            models.Index(fields=["user", "dedupe_key"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"

    def mark_read(self, save=True):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=["is_read", "read_at"])


class NotificationPreference(models.Model):
    """User notification preferences"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preference"
    )

    # Email preferences
    email_on_job_match = models.BooleanField(default=True)
    email_on_application_update = models.BooleanField(default=True)
    email_on_forum_reply = models.BooleanField(default=False)

    # In-app toggle
    in_app_notifications = models.BooleanField(default=True)

    # Frequency options
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ("instant", "Instant"),
            ("daily", "Daily Digest"),
            ("weekly", "Weekly Digest"),
        ],
        default="instant",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_preference"

    def __str__(self):
        return f"Notification Preferences for {self.user.username}"