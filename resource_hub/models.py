from django.db import models
from django.conf import settings


class Resource(models.Model):
    CATEGORY_CHOICES = [
        ('AI_ML', 'AI & Machine Learning'),
        ('WEB_DEV', 'Web Development'),
        ('APP_DEV', 'App Development'),
        ('CLOUD_AWS', 'Cloud & AWS'),
        ('PROGRAMMING', 'Programming'),
        ('DATA_SCIENCE', 'Data Science'),
    ]
    LEVEL_CHOICES = [
        ('BEGINNER', 'Beginner'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('ALL', 'All Levels'),
    ]
    RESOURCE_TYPE_CHOICES = [
        ('VIDEO', 'Video'),
        ('COURSE', 'Course'),
        ('ARTICLE', 'Article'),
        ('PLAYLIST', 'Playlist'),
        ('BOOTCAMP', 'Bootcamp'),
    ]
    PLATFORM_CHOICES = [
        ('YouTube', 'YouTube'),
        ('Khan Academy', 'Khan Academy'),
        ('freeCodeCamp', 'freeCodeCamp'),
        ('Harvard CS50', 'Harvard CS50'),
        ('MIT OCW', 'MIT OpenCourseWare'),
        ('fast.ai', 'fast.ai'),
        ('The Odin Project', 'The Odin Project'),
        ('Kaggle', 'Kaggle'),
        ('Google', 'Google'),
        ('AWS', 'AWS Skill Builder'),
        ('Microsoft Learn', 'Microsoft Learn'),
        ('Flutter', 'Flutter'),
        ('Other', 'Other'),
    ]

    title            = models.CharField(max_length=200)
    description      = models.TextField()
    url              = models.URLField(unique=True)
    platform         = models.CharField(max_length=100, choices=PLATFORM_CHOICES)
    category         = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    level            = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='ALL')
    resource_type    = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)
    is_free          = models.BooleanField(default=True)
    thumbnail_url    = models.URLField(blank=True)
    youtube_video_id = models.CharField(max_length=50, blank=True)
    duration         = models.CharField(max_length=50, blank=True)
    tags             = models.CharField(max_length=500, blank=True)
    view_count       = models.IntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-view_count', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.platform})"

    def get_tags_list(self):
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]


class Bookmark(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    resource   = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'resource']
        ordering = ['-created_at']


class UserProgress(models.Model):
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress')
    resource     = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='progress')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'resource']


class CVSkillGap(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skill_gaps')
    skill_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']