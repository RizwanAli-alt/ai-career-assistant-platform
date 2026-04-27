from .models import Notification, UserProfile


def notifications_count(request):
    """
    Injects `unread_count` into every template context.
    Used by base.html navbar bell icon.
    """
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return {"unread_count": count}
    return {"unread_count": 0}


def role_badge_color(request):
    """
    Injects `user_role` and `user_role_color` into every template context.
    Used by base.html to render the role badge next to the username.

    Colors match CareerAI frontend:
        student  → electric blue  #3B82F6
        senior   → purple         #7C3AED
        employer → green          #10B981
        mentor   → amber/yellow   #F59E0B
    """
    ROLE_COLORS = {
        "student":  "#3B82F6",
        "senior":   "#7C3AED",
        "employer": "#10B981",
        "mentor":   "#F59E0B",
    }

    if request.user.is_authenticated:
        try:
           role = request.user.community_profile.role
           return {
           "user_role":       role,
           "user_role_color": ROLE_COLORS.get(role, "#6B7280"),
           "user_role_label": request.user.community_profile.get_role_display(),
}
        except (UserProfile.DoesNotExist, AttributeError):
            pass

    return {
        "user_role":       "",
        "user_role_color": "#6B7280",
        "user_role_label": "",
    }