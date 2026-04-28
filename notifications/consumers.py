import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Notification


class NotificationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f"notifications_user_{user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        unread = await self._get_unread_count()
        await self.send(text_data=json.dumps({"type": "unread_count", "unread": unread}))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Optional: client can request refresh
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except Exception:
            return

        if data.get("action") == "get_unread_count":
            unread = await self._get_unread_count()
            await self.send(text_data=json.dumps({"type": "unread_count", "unread": unread}))

    async def notification_created(self, event):
        # event payload already contains notification
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _get_unread_count(self):
        return Notification.objects.filter(
            user=self.user, is_archived=False, is_read=False
        ).count()