from django.urls import path
from . import views

urlpatterns = [
    path("", views.notifications, name="notifications"),
    path("<int:notification_id>/read/", views.mark_as_read, name="mark_as_read"),
    path("<int:notification_id>/archive/", views.archive_notification, name="archive_notification"),
    path("mark-all-read/", views.mark_all_as_read, name="mark_all_as_read"),
    path("archive-all-read/", views.archive_all_read, name="archive_all_read"),
    path("preferences/", views.notification_preferences, name="notification_preferences"),
]