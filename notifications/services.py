from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from .models import Notification, NotificationPreference


def get_or_create_preferences(user: User) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def can_send_in_app(user: User) -> bool:
    prefs = get_or_create_preferences(user)
    return bool(prefs.in_app_notifications)


@transaction.atomic
def notify_user(
    *,
    user: User,
    notification_type: str,
    title: str,
    message: str,
    icon: str = "fa-bell",
    related_url: str | None = None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
    dedupe_window_seconds: int = 300,
) -> Notification | None:
    if not can_send_in_app(user):
        return None

    if dedupe_key:
        cutoff = timezone.now() - timezone.timedelta(seconds=dedupe_window_seconds)
        if Notification.objects.filter(
            user=user, dedupe_key=dedupe_key, created_at__gte=cutoff
        ).exists():
            return None

    notif = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        icon=icon,
        related_url=related_url,
        metadata=metadata or {},
        dedupe_key=dedupe_key,
    )

    # Real-time push (Channels). If Channels isn't installed/configured, ignore.
    try:
        from .realtime import push_notification_to_user  # noqa: PLC0415

        push_notification_to_user(notif)
    except Exception:  # noqa: BLE001
        pass

    return notif