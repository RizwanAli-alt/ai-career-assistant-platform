from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def push_notification_to_user(notification: Notification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    group = f"notifications_user_{notification.user_id}"

    payload = {
        "type": "notification",
        "id": notification.id,
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "icon": notification.icon,
        "related_url": notification.related_url,
        "created_at": notification.created_at.isoformat(),
        "is_read": notification.is_read,
        "unread_count_hint": None,  # optional (you can compute if needed)
        "metadata": getattr(notification, "metadata", {}) or {},
    }

    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "notification_created",
            "payload": payload,
        },
    )