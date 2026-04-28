from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Notification, NotificationPreference


@login_required(login_url="login")
@require_http_methods(["GET"])
def notifications(request):
    qs = (
        Notification.objects.filter(user=request.user, is_archived=False)
        .only("id", "title", "message", "icon", "related_url", "is_read", "created_at")
        .order_by("-created_at")
    )
    unread_count = qs.filter(is_read=False).count()

    paginator = Paginator(qs, 20)  # 20 per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "notifications": page_obj.object_list,
        "page_obj": page_obj,
        "unread_count": unread_count,
    }
    return render(request, "notifications/notifications.html", context)


@login_required(login_url="login")
@require_http_methods(["POST"])
def mark_as_read(request, notification_id):
    notification = get_object_or_404(
        Notification, pk=notification_id, user=request.user, is_archived=False
    )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return JsonResponse({"success": True})


@login_required(login_url="login")
@require_http_methods(["POST"])
def archive_notification(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    if not notification.is_archived:
        notification.is_archived = True
        notification.save(update_fields=["is_archived"])
    return JsonResponse({"success": True})


@login_required(login_url="login")
@require_http_methods(["POST"])
def mark_all_as_read(request):
    updated = (
        Notification.objects.filter(user=request.user, is_archived=False, is_read=False)
        .update(is_read=True, read_at=timezone.now())
    )
    return JsonResponse({"success": True, "updated": updated})


@login_required(login_url="login")
@require_http_methods(["POST"])
def archive_all_read(request):
    updated = (
        Notification.objects.filter(user=request.user, is_archived=False, is_read=True)
        .update(is_archived=True)
    )
    return JsonResponse({"success": True, "updated": updated})


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def notification_preferences(request):
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == "POST":
        preferences.email_on_job_match = request.POST.get("email_on_job_match") == "on"
        preferences.email_on_application_update = (
            request.POST.get("email_on_application_update") == "on"
        )
        preferences.email_on_forum_reply = request.POST.get("email_on_forum_reply") == "on"
        preferences.in_app_notifications = request.POST.get("in_app_notifications") == "on"
        preferences.notification_frequency = request.POST.get(
            "notification_frequency", "instant"
        )
        preferences.save()

        messages.success(request, "Notification preferences updated!")
        return redirect("notification_preferences")

    return render(request, "notifications/preferences.html", {"preferences": preferences})