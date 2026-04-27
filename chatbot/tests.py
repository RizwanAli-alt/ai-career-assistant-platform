from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ChatMessage, ChatSession, UserFeedback


class ChatbotViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='alice', password='testpass123')
        self.other_user = user_model.objects.create_user(username='bob', password='testpass123')

    def test_chat_requires_login(self):
        response = self.client.get(reverse('chat'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_feedback_only_on_own_messages(self):
        self.client.login(username='alice', password='testpass123')

        other_session = ChatSession.objects.create(user=self.other_user)
        other_bot_message = ChatMessage.objects.create(
            session=other_session,
            message_type='bot',
            content='Bot response for another user',
        )

        response = self.client.post(
            reverse('submit_feedback', args=[other_bot_message.id]),
            data={'rating': 4, 'comment': 'Good answer'},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(UserFeedback.objects.count(), 0)
