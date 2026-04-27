from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings

from .models import UserProfile, Post, Reply, Like, Badge, UserBadge, Notification


# ─────────────────────────────────────────────
#  HELPER: Award points + check badge milestones
# ─────────────────────────────────────────────
def award_points(user, points):
    try:
        profile = user.community_profile  # ← was user.userprofile
    except UserProfile.DoesNotExist:
        return

    profile.points += points
    profile.save(update_fields=["points"])

    _check_badge_milestones(user, profile.points)


def _check_badge_milestones(user, current_points):
    """
    Award every badge whose points_required threshold the user
    has just reached or passed — and hasn't already earned.
    """
    eligible_badges = Badge.objects.filter(
        points_required__lte=current_points
    )
    already_earned = UserBadge.objects.filter(
        user=user
    ).values_list("badge_id", flat=True)

    for badge in eligible_badges:
        if badge.id not in already_earned:
            UserBadge.objects.create(user=user, badge=badge)
            # Notify the user about their new badge
            Notification.objects.create(
                user=user,
                message=f"🏅 You earned the '{badge.name}' badge! ({badge.icon})",
                link="/community/profile/",
            )


def _create_notification(user, message, link=""):
    """Thin wrapper so we don't repeat Notification.objects.create everywhere."""
    Notification.objects.create(user=user, message=message, link=link)


# ─────────────────────────────────────────────
#  SIGNAL 1: Auto-create UserProfile on User creation
# ─────────────────────────────────────────────
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.community_profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


# ─────────────────────────────────────────────
#  SIGNAL 2: Post created → +10 points
# ─────────────────────────────────────────────
@receiver(post_save, sender=Post)
def post_created_handler(sender, instance, created, **kwargs):
    if not created:
        return  # Only fire on creation, not on every save/edit

    points = getattr(settings, "COMMUNITY_POINTS", {}).get("post_created", 10)
    award_points(instance.author, points)

    # Notify the author (confirmation that their post is live)
    _create_notification(
        user=instance.author,
        message=f"✅ Your post '{instance.title[:60]}' is now live! You earned {points} points.",
        link=f"/community/post/{instance.pk}/",
    )


# ─────────────────────────────────────────────
#  SIGNAL 3: Reply created → +5 points to replier
#            + notification to post author
# ─────────────────────────────────────────────
@receiver(post_save, sender=Reply)
def reply_created_handler(sender, instance, created, **kwargs):
    if not created:
        return

    points = getattr(settings, "COMMUNITY_POINTS", {}).get("reply_given", 5)
    award_points(instance.author, points)

    # Notify post author (but not if they replied to their own post)
    post_author = instance.post.author
    if post_author != instance.author:
        _create_notification(
            user=post_author,
            message=(
                f"💬 {instance.author.username} replied to your post "
                f"'{instance.post.title[:50]}'."
            ),
            link=f"/community/post/{instance.post.pk}/",
        )

    # If this is a nested reply (parent exists), notify the parent reply author too
    if instance.parent and instance.parent.author != instance.author:
        _create_notification(
            user=instance.parent.author,
            message=(
                f"↩️ {instance.author.username} replied to your comment."
            ),
            link=f"/community/post/{instance.post.pk}/",
        )


# ─────────────────────────────────────────────
#  SIGNAL 4: Like saved → +2 points to content owner
#            + notification to content owner
# ─────────────────────────────────────────────
@receiver(post_save, sender=Like)
def like_handler(sender, instance, created, **kwargs):
    """
    Fires when a Like row is created OR when is_active is toggled.
    We only award points when is_active=True (like given).
    On unlike (is_active=False) we do NOT deduct points — keeps
    the system positive and avoids abuse via rapid like/unlike.
    """
    if not instance.is_active:
        return  # Unlike — no point change, no notification

    points = getattr(settings, "COMMUNITY_POINTS", {}).get("like_received", 2)

    # Determine who owns the liked content
    if instance.post:
        content_owner = instance.post.author
        content_label = f"post '{instance.post.title[:50]}'"
        link = f"/community/post/{instance.post.pk}/"
    elif instance.reply:
        content_owner = instance.reply.author
        content_label = "your reply"
        link = f"/community/post/{instance.reply.post.pk}/"
    else:
        return  # Malformed like — neither post nor reply

    # Don't award points or notify if user liked their own content
    # (business rule: users cannot like their own posts/replies)
    if instance.user == content_owner:
        return

    # Only award points on first like (created=True), not on re-activation
    if created:
        award_points(content_owner, points)

    # Always notify on active like (throttle can be added later via Redis)
    _create_notification(
        user=content_owner,
        message=f"❤️ {instance.user.username} liked your {content_label}.",
        link=link,
    )