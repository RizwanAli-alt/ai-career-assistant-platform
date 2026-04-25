"""
Celery tasks for the Auto-Apply Agent.

Celery is an optional dependency.  If it is not installed the module loads
without error but tasks are plain Python callables (no async dispatch).
"""

try:
    from celery import shared_task

    CELERY_AVAILABLE = True
except ImportError:  # pragma: no cover
    CELERY_AVAILABLE = False

    def shared_task(func):  # type: ignore[misc]
        """No-op decorator used when Celery is absent."""
        return func


from django.contrib.auth.models import User

from .auto_apply import run_auto_apply
from .cover_letter import generate_cover_letter
from .models import ApplicationQueue, AutoApplyPermission, Job


@shared_task
def scheduled_auto_apply():
    """
    Run auto-apply for every user who has permission.allowed = True.
    Intended to be called every 2 hours via Celery Beat.
    """
    enabled = AutoApplyPermission.objects.filter(allowed=True).select_related("user")
    summary = {}
    for perm in enabled:
        result = run_auto_apply(perm.user)
        summary[perm.user.username] = result

        submitted = result.get("results", {}).get("submitted", 0)
        failed = result.get("results", {}).get("failed", 0)
        if submitted > 0 or failed > 0:
            _notify(
                perm.user,
                "Auto-Apply completed",
                f"{submitted} submitted, {failed} failed.",
            )
    return summary


@shared_task
def add_matched_jobs_to_queue(user_id):
    """
    Score active jobs against a user's CV skills and add matches
    (score ≥ 30 %) to ApplicationQueue as 'pending'.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return {"error": "User not found"}

    profile = getattr(user, "profile", None)
    if not profile or not profile.skills:
        return {"status": "no_skills", "added": 0}

    user_skills = [s.strip().lower() for s in profile.skills.split(",") if s.strip()]
    added = 0

    for job in Job.objects.filter(status="active"):
        job_skills = [s.lower() for s in job.get_required_skills_list()]
        if not job_skills:
            continue

        matching = [
            s for s in user_skills
            if any(s in js or js in s for js in job_skills)
        ]
        match_score = (len(matching) / len(job_skills)) * 100
        if match_score < 30:
            continue

        _, created = ApplicationQueue.objects.get_or_create(
            user=user,
            job=job,
            defaults={
                "match_score": match_score,
                "status": "pending",
                "cover_letter": generate_cover_letter(user, job),
            },
        )
        if created:
            added += 1

    if added > 0:
        _notify(
            user,
            "New jobs in your queue",
            f"{added} matched job(s) added to your approval queue.",
        )

    return {"status": "done", "added": added}


# ─── internal helper ──────────────────────────────────────────────────────────

def _notify(user, title, message):
    """Create an in-app notification silently (swallows any import errors)."""
    try:
        from notifications.models import Notification  # noqa: PLC0415

        Notification.objects.create(
            user=user,
            notification_type="alert",
            title=title,
            message=message,
        )
    except Exception:  # noqa: BLE001
        pass
