"""
Auto-Apply Agent – core logic.

run_auto_apply(user)   – check permissions, iterate approved queue, submit
submit_application(…)  – Selenium headless Chrome form filler
"""

import time

from django.utils import timezone

from .cover_letter import generate_cover_letter
from .models import ApplicationQueue, AuditLog, AutoApplyPermission


# ─── helpers ──────────────────────────────────────────────────────────────────

def get_or_create_permission(user):
    """Return (or lazily create) the AutoApplyPermission for *user*."""
    permission, _ = AutoApplyPermission.objects.get_or_create(user=user)
    return permission


# ─── main entry-point ─────────────────────────────────────────────────────────

def run_auto_apply(user):
    """
    Check permissions, iterate approved queue items and submit applications.

    Returns a dict with status and result counters.
    """
    permission = get_or_create_permission(user)

    if not permission.allowed:
        return {"status": "disabled", "message": "Auto-apply is not enabled."}

    if not permission.terms_accepted:
        return {"status": "terms_required", "message": "Terms not accepted."}

    today = timezone.now().date()
    submitted_today = ApplicationQueue.objects.filter(
        user=user,
        status="submitted",
        applied_at__date=today,
    ).count()

    if submitted_today >= permission.daily_limit:
        return {
            "status": "limit_reached",
            "message": f"Daily limit of {permission.daily_limit} reached.",
            "count": submitted_today,
        }

    approved_queue = ApplicationQueue.objects.filter(
        user=user, status="approved"
    ).select_related("job", "job__company")

    results = {"submitted": 0, "failed": 0, "skipped": 0}

    for queue_item in approved_queue:
        if submitted_today >= permission.daily_limit:
            results["skipped"] += 1
            continue

        # Generate (or refresh) cover letter
        cover_letter = generate_cover_letter(user, queue_item.job)
        queue_item.cover_letter = cover_letter

        profile = getattr(user, "profile", None)
        cv_path = profile.cv.path if (profile and profile.cv) else None

        # Build an apply URL; real implementations would store it on the Job model
        apply_url = (
            getattr(queue_item.job, "apply_url", None)
            or f"https://example.com/apply/{queue_item.job.pk}"
        )

        success, failure_reason = submit_application(apply_url, user, cv_path, cover_letter)

        if success:
            queue_item.status = "submitted"
            queue_item.applied_at = timezone.now()
            results["submitted"] += 1
            submitted_today += 1
            AuditLog.objects.create(
                user=user,
                job=queue_item.job,
                action="auto_apply_submitted",
                status="success",
                detail=(
                    f"Auto-applied to {queue_item.job.title} "
                    f"at {queue_item.job.company.name}"
                ),
            )
        else:
            queue_item.status = "failed"
            queue_item.failure_reason = failure_reason
            results["failed"] += 1
            AuditLog.objects.create(
                user=user,
                job=queue_item.job,
                action="auto_apply_failed",
                status="failed",
                detail=failure_reason,
            )

        queue_item.save()

    return {"status": "done", "results": results}


# ─── Selenium form filler ─────────────────────────────────────────────────────

def submit_application(url, user, cv_path, cover_letter):
    """
    Use headless Chrome (Selenium) to fill and submit a job-application form.

    Returns (True, '') on success or (False, reason_string) on failure.
    Selenium is an optional dependency; a clear error is returned if absent.
    """
    try:
        from selenium import webdriver  # noqa: PLC0415
        from selenium.common.exceptions import (  # noqa: PLC0415
            NoSuchElementException,
            WebDriverException,
        )
        from selenium.webdriver.chrome.options import Options  # noqa: PLC0415
        from selenium.webdriver.common.by import By  # noqa: PLC0415
    except ImportError:
        return False, "Selenium not installed. Run: pip install selenium"

    profile = getattr(user, "profile", None)
    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    email = user.email
    phone = (profile.phone or "") if profile else ""

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        return False, f"ChromeDriver error: {exc}"

    try:
        driver.get(url)
        time.sleep(2)

        def _fill(selectors, value):
            for sel in selectors:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    el.clear()
                    el.send_keys(value)
                    return True
                except NoSuchElementException:
                    pass
            return False

        # Name
        _fill(
            ['input[name="name"]', 'input[id*="name"]', 'input[placeholder*="name" i]'],
            full_name,
        )
        # Email
        _fill(
            ['input[type="email"]', 'input[name="email"]', 'input[id*="email"]'],
            email,
        )
        # Phone
        if phone:
            _fill(
                ['input[type="tel"]', 'input[name="phone"]', 'input[placeholder*="phone" i]'],
                phone,
            )
        # CV upload
        if cv_path:
            _fill(
                ['input[type="file"]', 'input[name="resume"]', 'input[name="cv"]'],
                cv_path,
            )
        # Cover letter
        _fill(
            [
                'textarea[name*="cover"]',
                'textarea[id*="cover"]',
                'textarea[placeholder*="cover" i]',
                "textarea",
            ],
            cover_letter,
        )

        # Submit
        for sel in [
            'button[type="submit"]',
            'input[type="submit"]',
            'button[id*="submit"]',
            'button[class*="submit"]',
        ]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(2)
                return True, ""
            except NoSuchElementException:
                pass

        return False, "Could not locate the submit button on this page."

    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        driver.quit()
