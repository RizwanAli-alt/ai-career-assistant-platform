# jobs/views.py
"""
Jobs Views — Full integration with scraper, CV analyzer, and Auto-Apply agent.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
import json
import logging

from .models import (
    AuditLog,
    ApplicationQueue,
    AutoApplyPermission,
    Company,
    Job,
    JobApplication,
    JobAlert,
    JobMatchScore,
    SavedJob,
)
from .forms import JobSearchForm, JobApplicationForm, SaveJobForm, JobAlertForm

# ── Scraper / Analyzer imports ────────────────────────────────────────────────
try:
    from scraper.orchestrator import ScraperOrchestrator
    from analyzer.skills import get_skill_extractor
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    logging.warning("Scraper modules not available.")

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# JOB LISTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def job_list(request):
    jobs = Job.objects.filter(status='active')
    form = JobSearchForm(request.GET)

    if form.is_valid():
        keyword = form.cleaned_data.get('keyword')
        if keyword:
            jobs = jobs.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(required_skills__icontains=keyword)
            )
        location = form.cleaned_data.get('location')
        if location:
            jobs = jobs.filter(location__icontains=location)
        job_types = form.cleaned_data.get('job_type')
        if job_types:
            jobs = jobs.filter(job_type__in=job_types)
        exp_levels = form.cleaned_data.get('experience_level')
        if exp_levels:
            jobs = jobs.filter(experience_level__in=exp_levels)
        salary_min = form.cleaned_data.get('salary_min')
        salary_max = form.cleaned_data.get('salary_max')
        if salary_min:
            jobs = jobs.filter(Q(salary_min__gte=salary_min) | Q(salary_min__isnull=True))
        if salary_max:
            jobs = jobs.filter(Q(salary_max__lte=salary_max) | Q(salary_max__isnull=True))
        sort_by = form.cleaned_data.get('sort_by')
        if sort_by == 'newest':
            jobs = jobs.order_by('-posted_date')
        elif sort_by == 'salary_high':
            jobs = jobs.order_by('-salary_max')
        elif sort_by == 'salary_low':
            jobs = jobs.order_by('salary_min')

    paginator = Paginator(jobs, 10)
    jobs_page = paginator.get_page(request.GET.get('page'))

    return render(request, 'jobs/job_list.html', {
        'form': form,
        'jobs': jobs_page,
        'total_jobs': paginator.count,
    })


@require_http_methods(["GET"])
def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk)
    job.views_count += 1
    job.save(update_fields=['views_count'])

    user_applied = job_saved = False
    match_score = None
    if request.user.is_authenticated:
        user_applied = JobApplication.objects.filter(user=request.user, job=job).exists()
        job_saved = SavedJob.objects.filter(user=request.user, job=job).exists()
        match_score = JobMatchScore.objects.filter(user=request.user, job=job).first()

    return render(request, 'jobs/job_detail.html', {
        'job': job,
        'user_applied': user_applied,
        'job_saved': job_saved,
        'match_score': match_score,
    })


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def apply_job(request, pk):
    job = get_object_or_404(Job, pk=pk)
    existing = JobApplication.objects.filter(user=request.user, job=job).first()
    if existing:
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', pk=job.pk)

    if request.method == 'POST':
        form = JobApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.job = job
            application.save()
            job.applicants_count += 1
            job.save(update_fields=['applicants_count'])
            messages.success(request, 'Application submitted successfully!')
            return redirect('job_detail', pk=job.pk)
    else:
        form = JobApplicationForm()

    return render(request, 'jobs/apply_job.html', {'form': form, 'job': job})


@login_required(login_url='login')
@require_http_methods(["POST"])
def save_job(request, pk):
    job = get_object_or_404(Job, pk=pk)
    _, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    messages.success(request, 'Job saved!' if created else 'Already saved.')
    return redirect('job_detail', pk=job.pk)


@login_required(login_url='login')
@require_http_methods(["POST"])
def unsave_job(request, pk):
    job = get_object_or_404(Job, pk=pk)
    SavedJob.objects.filter(user=request.user, job=job).delete()
    messages.success(request, 'Job removed from saved.')
    return redirect('job_detail', pk=job.pk)


@login_required(login_url='login')
@require_http_methods(["GET"])
def saved_jobs(request):
    saved_qs = SavedJob.objects.filter(user=request.user).select_related('job')
    paginator = Paginator(saved_qs, 10)
    return render(request, 'jobs/saved_jobs.html', {
        'saved_jobs': paginator.get_page(request.GET.get('page')),
        'total_saved': paginator.count,
    })


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_applications(request):
    applications = JobApplication.objects.filter(user=request.user).select_related('job', 'job__company')
    status = request.GET.get('status')
    if status:
        applications = applications.filter(status=status)
    paginator = Paginator(applications, 10)
    return render(request, 'jobs/my_applications.html', {
        'applications': paginator.get_page(request.GET.get('page')),
        'total_applications': paginator.count,
        'status_filter': status,
        'status_choices': JobApplication._meta.get_field('status').choices,
    })


@login_required(login_url='login')
@require_http_methods(["GET"])
def application_detail(request, pk):
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    return render(request, 'jobs/applications_details.html', {
        'application': application,
        'job': application.job,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# JOB ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def create_job_alert(request):
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, 'Job alert created!')
            return redirect('my_job_alerts')
    else:
        form = JobAlertForm()
    return render(request, 'jobs/create_job_alerts.html', {'form': form})


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_job_alerts(request):
    alerts = JobAlert.objects.filter(user=request.user)
    return render(request, 'jobs/my_jobs_alerts.html', {
        'alerts': alerts,
        'total_alerts': alerts.count(),
    })


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_job_alert(request, pk):
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.delete()
    messages.success(request, 'Alert deleted.')
    return redirect('my_job_alerts')


# ═══════════════════════════════════════════════════════════════════════════════
# COMPANIES
# ═══════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def companies(request):
    companies_qs = Company.objects.all()
    search = request.GET.get('search')
    if search:
        companies_qs = companies_qs.filter(
            Q(name__icontains=search) |
            Q(industry__icontains=search) |
            Q(location__icontains=search)
        )
    paginator = Paginator(companies_qs, 12)
    return render(request, 'jobs/companies.html', {
        'companies': paginator.get_page(request.GET.get('page')),
        'total_companies': paginator.count,
        'search_query': search,
    })


@require_http_methods(["GET"])
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    jobs = Job.objects.filter(company=company, status='active')
    return render(request, 'jobs/company_detail.html', {
        'company': company,
        'jobs': jobs,
        'total_jobs': jobs.count(),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED JOBS
# ═══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='login')
@require_http_methods(["GET"])
def recommended_jobs(request):
    try:
        from cv_analyzer.models import CVAnalysis
        cv_analysis = CVAnalysis.objects.filter(
            user=request.user, is_analyzed=True
        ).latest('created_at')
        skills = json.loads(cv_analysis.extracted_skills) if cv_analysis.extracted_skills else {}
        user_technical_skills = skills.get('technical', [])
    except Exception:
        messages.info(request, 'Analyze your CV first for recommendations.')
        return redirect('upload_cv_analysis')

    if not user_technical_skills:
        messages.warning(request, 'No skills detected in your CV.')
        return redirect('cv_analysis_detail', pk=cv_analysis.pk)

    jobs = Job.objects.filter(status='active')
    jobs_with_scores = []
    for job in jobs:
        job_skills = set(s.lower() for s in job.get_required_skills_list())
        user_set = set(s.lower() for s in user_technical_skills)
        job.match_percentage = int((len(job_skills & user_set) / len(job_skills)) * 100) if job_skills else 0
        jobs_with_scores.append(job)

    jobs_with_scores.sort(key=lambda x: x.match_percentage, reverse=True)
    paginator = Paginator(jobs_with_scores, 10)
    return render(request, 'jobs/recommended_jobs.html', {
        'jobs': paginator.get_page(request.GET.get('page')),
        'total_jobs': len(jobs_with_scores),
        'user_skills_count': len(user_technical_skills),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SMART JOB SEARCH WITH SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='login')
@require_http_methods(["GET"])
def job_search_with_scraper(request):
    """Search jobs via multi-portal scraper with CV-based match scoring."""

    if not SCRAPER_AVAILABLE:
        messages.error(request, '❌ Scraper modules not installed.')
        return redirect('job_list')

    # ── Load user CV skills ────────────────────────────────────────────────
    cv_skills = {'technical': [], 'soft': []}
    has_cv_analysis = False
    user_skills = []
    cv_analysis = None

    try:
        from cv_analyzer.models import CVAnalysis
        cv_analysis = CVAnalysis.objects.filter(
            user=request.user, is_analyzed=True
        ).latest('created_at')
        cv_skills = json.loads(cv_analysis.extracted_skills) if cv_analysis.extracted_skills else cv_skills
        has_cv_analysis = True
        user_skills = cv_skills.get('technical', [])[:8]
    except Exception:
        pass

    if not has_cv_analysis:
        messages.warning(request, '⚠️ No CV analyzed — jobs shown without match scores.')

    # ── Handle search ──────────────────────────────────────────────────────
    scraped_jobs = []
    search_performed = False
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    demo_mode = request.GET.get('demo', 'true').lower() == 'true'

    if query:
        search_performed = True
        try:
            # Load skill_db for richer skills_mentioned extraction
            skill_db = None
            if has_cv_analysis:
                try:
                    skill_db = get_skill_extractor().skill_db
                except Exception as e:
                    logger.warning(f"skill_db load failed: {e}")

            orchestrator = ScraperOrchestrator(skill_db=skill_db)
            scraped_jobs = orchestrator.run(
                query=query,
                location=location or None,
                portals=['LinkedIn', 'Indeed', 'Rozee.pk'],
                user_skills=cv_skills if has_cv_analysis else {},
                max_per_portal=10,
                demo_mode=demo_mode,
                force_refresh=request.GET.get('refresh') == 'true',
            )

            # ── Persist scraped jobs to Django DB ─────────────────────────
            for jd in scraped_jobs:
                try:
                    company, _ = Company.objects.get_or_create(
                        name=jd.company,
                        defaults={
                            'location': jd.location or 'Not specified',
                            'industry': 'Technology',
                        }
                    )
                    job_obj, created = Job.objects.get_or_create(
                        title=jd.title,
                        company=company,
                        location=jd.location,
                        defaults={
                            'description': jd.description or '',
                            'job_type': 'full-time',
                            'experience_level': 'mid',
                            'required_skills': ', '.join(jd.skills_mentioned)[:500],
                            'status': 'active',
                        }
                    )
                    if has_cv_analysis:
                        JobMatchScore.objects.update_or_create(
                            user=request.user,
                            job=job_obj,
                            defaults={
                                'overall_match': jd.match_score,
                                'skills_match': jd.match_score,
                            }
                        )
                except Exception as e:
                    logger.warning(f"DB persist error for '{jd.title}': {e}")

            mode_label = 'Demo' if demo_mode else 'Live'
            messages.success(
                request,
                f'✅ {mode_label}: found {len(scraped_jobs)} jobs for "{query}".'
                + (' Matched against your CV.' if has_cv_analysis else '')
            )
            logger.info(f"Scraper: {len(scraped_jobs)} results | query={query} | demo={demo_mode}")

        except Exception as e:
            logger.exception(f"Scraper orchestrator error: {e}")
            messages.error(request, f'Search failed: {e}')

    # ── Paginate scraped_jobs (list of JobListing dataclass objects) ───────
    paginator = Paginator(scraped_jobs, 15)
    jobs_page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'jobs/job_search_with_scraper.html', {
        'jobs': jobs_page,
        'total_jobs': len(scraped_jobs),
        'search_performed': search_performed,
        'has_cv_analysis': has_cv_analysis,
        'user_skills': user_skills,
        'demo_mode': demo_mode,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-APPLY AGENT
# ═══════════════════════════════════════════════════════════════════════════════

def _get_or_create_permission(user):
    permission, _ = AutoApplyPermission.objects.get_or_create(user=user)
    return permission


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def auto_apply_settings(request):
    permission = _get_or_create_permission(request.user)

    if request.method == 'POST':
        terms_accepted   = request.POST.get('terms_accepted') == 'on'
        allowed          = request.POST.get('allowed') == 'on'
        require_approval = request.POST.get('require_approval') == 'on'
        try:
            daily_limit = max(1, min(50, int(request.POST.get('daily_limit', 10))))
        except (ValueError, TypeError):
            daily_limit = 10

        if allowed and not terms_accepted:
            messages.error(request, 'You must accept the terms to enable Auto-Apply.')
            return redirect('auto_apply_settings')

        permission.terms_accepted   = terms_accepted
        permission.allowed          = allowed
        permission.require_approval = require_approval
        permission.daily_limit      = daily_limit
        if allowed and not permission.granted_at:
            permission.granted_at = timezone.now()
        elif not allowed:
            permission.granted_at = None
        permission.save()

        AuditLog.objects.create(
            user=request.user,
            action='settings_updated',
            status='success',
            detail=f'allowed={allowed}, daily_limit={daily_limit}, require_approval={require_approval}',
        )
        messages.success(request, 'Auto-Apply settings saved.')
        return redirect('auto_apply_settings')

    today = timezone.now().date()
    applied_today = ApplicationQueue.objects.filter(
        user=request.user, status='submitted', applied_at__date=today
    ).count()
    pending_count = ApplicationQueue.objects.filter(user=request.user, status='pending').count()
    total_applied = ApplicationQueue.objects.filter(user=request.user, status='submitted').count()

    queue_items = (
        ApplicationQueue.objects
        .filter(user=request.user, status='pending')
        .select_related('job', 'job__company')
        .order_by('-match_score')
    )
    history_qs = (
        ApplicationQueue.objects
        .filter(user=request.user, status__in=['submitted', 'failed', 'rejected'])
        .select_related('job', 'job__company')
    )
    history = Paginator(history_qs, 20).get_page(request.GET.get('page'))

    return render(request, 'jobs/auto_apply.html', {
        'permission':    permission,
        'applied_today': applied_today,
        'pending_count': pending_count,
        'total_applied': total_applied,
        'queue_items':   queue_items,
        'history':       history,
    })


@login_required(login_url='login')
@require_http_methods(["POST"])
def run_apply(request):
    """Manually trigger the auto-apply agent for the current user."""
    permission = _get_or_create_permission(request.user)

    if not permission.allowed:
        messages.error(request, '❌ Enable Auto-Apply in settings first.')
        return redirect('auto_apply_settings')
    if not permission.terms_accepted:
        messages.error(request, '❌ Accept the terms before running the agent.')
        return redirect('auto_apply_settings')

    try:
        from .auto_apply import run_auto_apply
        result = run_auto_apply(request.user)
        status = result.get('status')

        if status == 'done':
            r = result.get('results', {})
            messages.success(
                request,
                f"✅ Agent finished — {r.get('submitted', 0)} submitted, "
                f"{r.get('failed', 0)} failed, {r.get('skipped', 0)} skipped."
            )
        elif status == 'limit_reached':
            messages.warning(request, f"⚠️ Daily limit reached ({result.get('count', 0)} applications).")
        else:
            messages.info(request, f"Agent status: {status} — {result.get('message', '')}")

    except Exception as e:
        logger.exception(f"run_apply error: {e}")
        messages.error(request, f'Agent error: {e}')

    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def approve_job(request, pk):
    item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    if item.status == 'pending':
        item.status = 'approved'
        item.save()
        AuditLog.objects.create(
            user=request.user, job=item.job,
            action='job_approved', status='approved',
            detail=f'Approved: {item.job.title}',
        )
        messages.success(request, f'✅ "{item.job.title}" approved.')
    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def reject_job(request, pk):
    item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    if item.status in ('pending', 'approved'):
        item.status = 'rejected'
        item.save()
        AuditLog.objects.create(
            user=request.user, job=item.job,
            action='job_rejected', status='rejected',
            detail=f'Rejected: {item.job.title}',
        )
        messages.info(request, f'"{item.job.title}" rejected.')
    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_cv_analysis(request, pk):
    from cv_analyzer.models import CVAnalysis
    analysis = get_object_or_404(CVAnalysis, pk=pk, user=request.user)
    analysis.delete()
    messages.success(request, '✅ CV analysis deleted.')
    return redirect('cv_analysis_list')