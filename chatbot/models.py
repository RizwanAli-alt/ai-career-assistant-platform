from django.db import models
from django.conf import settings
import json

class ChatSession(models.Model):
    """Model for chat sessions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, default='New Chat')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chatbot_chat_session'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class ChatMessage(models.Model):
    """Model for chat messages"""
    MESSAGE_TYPE = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Bot specific
    confidence_score = models.FloatField(default=0)  # 0-1
    intent = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'chatbot_chat_message'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.message_type} - {self.content[:50]}"


class FAQCategory(models.Model):
    """Model for FAQ categories"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # Font Awesome icon
    order = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'chatbot_faq_category'
        verbose_name_plural = 'FAQ Categories'
        ordering = ['order']
    
    def __str__(self):
        return self.name


class FAQ(models.Model):
    """Model for FAQs"""
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=300)
    answer = models.TextField()
    keywords = models.CharField(max_length=500, blank=True, null=True)  # Comma-separated
    views_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chatbot_faq'
        ordering = ['-views_count']
    
    def __str__(self):
        return self.question
    
    def get_keywords_list(self):
        if self.keywords:
            return [kw.strip().lower() for kw in self.keywords.split(',')]
        return []


class CareerTip(models.Model):
    """Model for career tips"""
    CATEGORY_CHOICES = [
        ('resume', 'Resume/CV'),
        ('interview', 'Interview'),
        ('salary', 'Salary Negotiation'),
        ('skills', 'Skills Development'),
        ('networking', 'Networking'),
        ('job_search', 'Job Search'),
        ('career_change', 'Career Change'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    image = models.ImageField(upload_to='career_tips/', blank=True, null=True)
    featured = models.BooleanField(default=False)
    views_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chatbot_career_tip'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class UserFeedback(models.Model):
    """Model for user feedback on bot responses"""
    RATING_CHOICES = [
        (1, 'Very Unhelpful'),
        (2, 'Unhelpful'),
        (3, 'Neutral'),
        (4, 'Helpful'),
        (5, 'Very Helpful'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bot_feedback')
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chatbot_user_feedback'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_rating_display()}"