"""
Jobs Module Views — Complete Integration with CV Analyzer & Scraper

Flow:
1. CHECK CV ANALYSIS → Get extracted_skills from CVAnalysis model
2. INITIALIZE SCRAPER → Create ScraperOrchestrator with skill_db
3. RUN SCRAPER → Call orchestrator.run() (demo or live)
4. SCORE JOBS → Matcher.score_and_sort() with CV skills
5. STORE IN DB → Save jobs + match scores to Django DB
6. RENDER FRONTEND → Display with match scores + filtering

Proper integration:
- ✅ Uses CVAnalysis.extracted_skills (JSON: technical + soft skills)
- ✅ Uses scraper/orchestrator.py for multi-portal scraping
- ✅ Uses matcher/scorer.py for CV matching
- ✅ Stores in JobMatchScore model
- ✅ Complete error handling & logging
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

import json
import time
import logging

from .models import (
    Job, Company, JobApplication, SavedJob, JobAlert, 
    JobMatchScore, AutoApplyPermission, ApplicationQueue, AuditLog
)
from .forms import JobSearchForm, JobApplicationForm, SaveJobForm, JobAlertForm
from .auto_apply import run_auto_apply

# Import CV Analyzer (for extracted skills)
from cv_analyzer.models import CVAnalysis

# Import Scraper & Matcher
from scraper.orchestrator import ScraperOrchestrator
from scraper.matcher import score_and_sort

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: CHECK CV ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────
# Helper function to get user's CV skills
# ══════════════════════════════════════════════════════════════════════════════

def _get_user_cv_skills(user, verbose=False):
    """
    STEP 1: CHECK CV ANALYSIS
    
    Retrieves user's extracted skills from most recent CVAnalysis.
    
    Returns:
    ├─ user_skills (dict): {'technical': [...], 'soft': [...]}
    ├─ has_cv_analysis (bool): True if CV analyzed
    ├─ cv_analysis (CVAnalysis): The model instance or None
    └─ user_skills_list (list): Top 5 technical skills for display
    
    Example:
    >>> user_skills, has_cv, cv, skills_list = _get_user_cv_skills(user)
    >>> print(f"Skills: {user_skills['technical']}")
    >>> print(f"Has CV: {has_cv}")
    """
    
    user_skills = {'technical': [], 'soft': []}
    has_cv_analysis = False
    cv_analysis = None
    user_skills_list = []
    
    try:
        # Get most recent analyzed CV
        cv_analysis = CVAnalysis.objects.filter(
            user=user,
            is_analyzed=True
        ).latest('created_at')
        
        # Parse extracted skills (stored as JSON)
        if cv_analysis.extracted_skills:
            try:
                user_skills = json.loads(cv_analysis.extracted_skills)
                # Ensure proper structure
                if not isinstance(user_skills, dict):
                    user_skills = {'technical': [], 'soft': []}
                if 'technical' not in user_skills:
                    user_skills['technical'] = []
                if 'soft' not in user_skills:
                    user_skills['soft'] = []
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in extracted_skills for user {user.username}")
                user_skills = {'technical': [], 'soft': []}
        
        has_cv_analysis = True
        # Get top 5 technical skills for display
        user_skills_list = user_skills.get('technical', [])[:5]
        
        if verbose:
            logger.info(
                f"✅ CV Analysis found for {user.username}: "
                f"{len(user_skills.get('technical', []))} technical, "
                f"{len(user_skills.get('soft', []))} soft skills"
            )
    
    except CVAnalysis.DoesNotExist:
        logger.warning(f"⚠️  No CV analysis found for user {user.username}")
        has_cv_analysis = False
        user_skills = {'technical': [], 'soft': []}
    
    except Exception as e:
        logger.error(f"Error retrieving CV skills: {e}")
        has_cv_analysis = False
        user_skills = {'technical': [], 'soft': []}
    
    return user_skills, has_cv_analysis, cv_analysis, user_skills_list


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VIEW: Job Search with Scraper (6-Step Flow)
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def job_search_with_scraper(request):
    """
    COMPLETE 6-STEP FLOW:
    
    1️⃣  CHECK CV ANALYSIS
        └─ Get extracted_skills from CVAnalysis model
    
    2️⃣  INITIALIZE SCRAPER
        └─ Create ScraperOrchestrator(skill_db)
    
    3️⃣  RUN SCRAPER
        ├─ Demo mode: instant mock data (~6 seconds)
        └─ Live mode: real scraping (~20-25 seconds)
    
    4️⃣  SCORE JOBS
        ├─ Match each job against CV skills
        └─ Sort by match score (highest first)
    
    5️⃣  STORE IN DB
        ├─ Create/Get Company
        ├─ Create/Get Job
        ├─ Create JobMatchScore
        └─ Store in Django DB for persistence
    
    6️⃣  RENDER FRONTEND
        ├─ Display job cards with match scores
        ├─ Portal filter tabs
        ├─ Pagination (15/page)
        └─ Full UI integration
    
    Parameters from GET:
    - q: Search query (required for search)
    - location: Job location (optional)
    - demo: 'true'/'false' for demo mode
    - refresh: 'true' to force refresh cache
    """
    
    logger.info(f"🔍 Job search initiated by {request.user.username}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: CHECK CV ANALYSIS
    # ──────────────────────────────────────────────────────────────���──────────
    
    user_skills, has_cv_analysis, cv_analysis, user_skills_list = _get_user_cv_skills(
        request.user, 
        verbose=True
    )
    
    if not has_cv_analysis:
        messages.warning(
            request,
            '📄 No CV analyzed yet. Analyze your CV first for personalized job matching! '
            'Visit: CV Analysis → Upload CV'
        )
    else:
        messages.info(
            request,
            f'✅ CV found! Using {len(user_skills.get("technical", []))} technical skills '
            f'for job matching.'
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Initialize variables
    # ─────────────────────────────────────────────────────────────────────────
    
    scraped_jobs = []
    search_performed = False
    demo_mode = True
    query = ""
    location = ""
    error_message = None
    scraper_stats = {}
    
    # ─────────────���───────────────────────────────────────────────────────────
    # STEP 2 & 3: INITIALIZE & RUN SCRAPER (if GET request with query)
    # ─────────────────────────────────────────────────────────────────────────
    
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()
        location = request.GET.get('location', '').strip()
        demo_values = request.GET.getlist('demo')
        if demo_values:
            demo_mode = any(value.lower() == 'true' for value in demo_values)
        else:
            demo_mode = True
        force_refresh = request.GET.get('refresh', 'false').lower() == 'true'
        
        if query:
            search_performed = True
            logger.info(
                f"🔎 Search: query='{query}', location='{location}', "
                f"demo={demo_mode}, refresh={force_refresh}"
            )
            
            try:
                # ─────────────────────────────────────────────────────────────
                # STEP 2: INITIALIZE SCRAPER
                # ─────────────────────────────────────────────────────────────
                
                start_time = time.time()
                
                # Get skill_db from analyzer
                skill_db = None
                try:
                    from analyzer.skills import get_skill_extractor
                    skill_extractor = get_skill_extractor()
                    skill_db = skill_extractor.skill_db
                    logger.info("✅ Skill database loaded from analyzer")
                except Exception as e:
                    logger.warning(f"Could not load skill DB: {e}")
                
                # Initialize orchestrator
                orchestrator = ScraperOrchestrator(skill_db=skill_db)
                logger.info("✅ ScraperOrchestrator initialized")
                
                # ─────────────────────────────────────────────────────────────
                # STEP 3: RUN SCRAPER
                # ─────────────────────────────────────────────────────────────
                
                scraped_jobs = orchestrator.run(
                    query=query,
                    location=location,
                    portals=['LinkedIn', 'Indeed', 'Rozee.pk'],
                    user_skills=user_skills if has_cv_analysis else {},
                    max_per_portal=8,  # 8 × 3 portals = 24 jobs
                    demo_mode=demo_mode,
                    force_refresh=force_refresh
                )
                
                elapsed = time.time() - start_time
                logger.info(
                    f"✅ Scraper complete: {len(scraped_jobs)} jobs in {elapsed:.1f}s "
                    f"(mode={'demo' if demo_mode else 'live'})"
                )
                
                # Store stats for template
                scraper_stats = {
                    'total_jobs': len(scraped_jobs),
                    'elapsed_time': round(elapsed, 1),
                    'mode': 'demo' if demo_mode else 'live',
                    'has_cache': not force_refresh,
                }
                
                if not scraped_jobs:
                    messages.warning(
                        request,
                        f'⚠️  No jobs found for "{query}" in {location or "any location"}. '
                        f'Try different keywords or location.'
                    )
                else:
                    # ─────────────────────────────────────────────────────────
                    # STEP 4: SCORE JOBS (already done in orchestrator.run())
                    # ─────────────────────────────────────────────────────────
                    
                    top_matches = [j for j in scraped_jobs if j.match_score >= 60]
                    logger.info(
                        f"📊 Scoring: {len(top_matches)} jobs with ≥60% match, "
                        f"top score: {max(j.match_score for j in scraped_jobs) if scraped_jobs else 0}%"
                    )
                    
                    # ─────────────────────────────────────────────────────────
                    # STEP 5: STORE IN DB
                    # ─────────────────────────────────────────────────────��───
                    
                    db_stored_count = 0
                    for job_data in scraped_jobs:
                        try:
                            # Create or get company
                            company, _ = Company.objects.get_or_create(
                                name=job_data.company,
                                defaults={
                                    'location': job_data.location or 'Not specified',
                                    'industry': 'Technology',
                                    'company_size': 'medium',
                                }
                            )
                            
                            # Create or get job
                            job, created = Job.objects.get_or_create(
                                title=job_data.title,
                                company=company,
                                location=job_data.location,
                                defaults={
                                    'description': job_data.description or 'No description',
                                    'job_type': 'full-time',
                                    'experience_level': 'mid',
                                    'required_skills': ','.join(job_data.skills_mentioned)[:500] if job_data.skills_mentioned else '',
                                    'status': 'active',
                                }
                            )
                            
                            # Store match score
                            if has_cv_analysis:
                                JobMatchScore.objects.update_or_create(
                                    user=request.user,
                                    job=job,
                                    defaults={
                                        'overall_match': job_data.match_score,
                                        'skills_match': job_data.match_score,
                                    }
                                )
                            
                            db_stored_count += 1
                        
                        except Exception as e:
                            logger.error(f"Error storing job '{job_data.title}': {e}")
                            continue
                    
                    logger.info(f"💾 Stored {db_stored_count}/{len(scraped_jobs)} jobs in DB")
                    
                    messages.success(
                        request,
                        f'✅ Found {len(scraped_jobs)} jobs! '
                        f'{len(top_matches)} are highly matched (≥60%). '
                        + ('Matched against your CV.' if has_cv_analysis else 'Analyze CV for better matching.')
                    )
            
            except Exception as e:
                logger.exception(f"❌ Scraper error: {e}")
                error_message = f'Search failed: {str(e)}'
                messages.error(request, error_message)
                scraped_jobs = []
    
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: RENDER FRONTEND (Pagination)
    # ─────────────────────────────────────────────────────────────────────────
    
    paginator = Paginator(scraped_jobs, 15)  # 15 jobs per page
    page_number = request.GET.get('page', 1)
    jobs_page = paginator.get_page(page_number)
    
    # Get portal breakdown
    portal_stats = {}
    if scraped_jobs:
        for job in scraped_jobs:
            portal = job.portal if hasattr(job, 'portal') else 'Unknown'
            portal_stats[portal] = portal_stats.get(portal, 0) + 1
    
    context = {
        # Search results
        'jobs': jobs_page,
        'total_jobs': len(scraped_jobs),
        'search_performed': search_performed,
        
        # Query info
        'query': query,
        'location': location,
        'demo_mode': demo_mode,
        
        # CV info
        'has_cv_analysis': has_cv_analysis,
        'cv_analysis': cv_analysis,
        'user_skills': user_skills_list,  # Top 5 for display
        'skills_count': {
            'technical': len(user_skills.get('technical', [])),
            'soft': len(user_skills.get('soft', [])),
        },
        
        # Stats
        'scraper_stats': scraper_stats,
        'portal_stats': portal_stats,
        'error_message': error_message,
        
        # Pagination
        'paginator': paginator,
        'page_obj': jobs_page,
    }
    
    logger.info(f"📄 Rendering template with {len(scraped_jobs)} jobs")
    return render(request, 'jobs/job_search_with_scraper.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# OTHER VIEWS (Job List, Detail, Apply, etc.)
# ═════════════════��════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def job_list(request):
    """Browse all jobs with filters."""
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
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)
    
    context = {'form': form, 'jobs': jobs_page}
    return render(request, 'jobs/job_list.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def job_detail(request, pk):
    """View job details with match score if CV analyzed."""
    job = get_object_or_404(Job, pk=pk)
    
    # Get user's CV skills for match display
    user_skills, has_cv, _, _ = _get_user_cv_skills(request.user)
    
    # Get match score if available
    match_score = 0
    try:
        if has_cv:
            match = JobMatchScore.objects.get(user=request.user, job=job)
            match_score = match.overall_match
    except JobMatchScore.DoesNotExist:
        pass
    
    # Check if user has applied
    has_applied = JobApplication.objects.filter(
        user=request.user, job=job
    ).exists()
    
    # Check if user has saved
    has_saved = SavedJob.objects.filter(
        user=request.user, job=job
    ).exists()
    
    context = {
        'job': job,
        'has_cv_analysis': has_cv,
        'match_score': match_score,
        'has_applied': has_applied,
        'has_saved': has_saved,
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def apply_job(request, pk):
    """Apply for a job."""
    job = get_object_or_404(Job, pk=pk)
    
    # Check if already applied
    existing = JobApplication.objects.filter(user=request.user, job=job).first()
    if existing:
        messages.warning(request, f'You already applied for "{job.title}".')
        return redirect('job_detail', pk=pk)
    
    if request.method == 'POST':
        form = JobApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.job = job
            application.save()
            
            job.applicants_count += 1
            job.save()
            
            messages.success(request, f'✅ Applied for "{job.title}"!')
            return redirect('job_detail', pk=pk)
    else:
        form = JobApplicationForm()
    
    context = {'form': form, 'job': job}
    return render(request, 'jobs/apply_job.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def save_job(request, pk):
    """Save a job."""
    job = get_object_or_404(Job, pk=pk)
    
    saved, created = SavedJob.objects.get_or_create(
        user=request.user,
        job=job,
        defaults={'notes': ''}
    )
    
    if created:
        messages.success(request, f'✅ Saved "{job.title}"!')
    else:
        messages.info(request, f'Already saved "{job.title}".')
    
    return redirect('job_detail', pk=pk)


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_applications(request):
    """View user's job applications."""
    applications = JobApplication.objects.filter(
        user=request.user
    ).select_related('job', 'job__company').order_by('-applied_date')
    
    paginator = Paginator(applications, 10)
    page_number = request.GET.get('page')
    apps_page = paginator.get_page(page_number)
    
    context = {'applications': apps_page}
    return render(request, 'jobs/my_applications.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def saved_jobs(request):
    """View saved jobs."""
    saved = SavedJob.objects.filter(
        user=request.user
    ).select_related('job', 'job__company').order_by('-saved_date')
    
    paginator = Paginator(saved, 10)
    page_number = request.GET.get('page')
    saved_page = paginator.get_page(page_number)
    
    context = {'saved_jobs': saved_page}
    return render(request, 'jobs/saved_jobs.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def recommended_jobs(request):
    """Get job recommendations based on CV skills."""
    user_skills, has_cv, cv_analysis, _ = _get_user_cv_skills(request.user)
    
    if not has_cv:
        messages.warning(request, 'Analyze your CV first for recommendations.')
        return redirect('upload_cv_analysis')
    
    # Get all active jobs and score them
    all_jobs = Job.objects.filter(status='active')
    
    recommendations = []
    for job in all_jobs:
        try:
            match_score = JobMatchScore.objects.get(
                user=request.user,
                job=job
            ).overall_match
        except JobMatchScore.DoesNotExist:
            match_score = 0
        
        if match_score >= 50:  # Only recommend 50%+ matches
            recommendations.append({
                'job': job,
                'match_score': match_score,
            })
    
    # Sort by match score
    recommendations.sort(key=lambda x: x['match_score'], reverse=True)
    
    paginator = Paginator(recommendations, 10)
    page_number = request.GET.get('page')
    recs_page = paginator.get_page(page_number)
    
    context = {
        'recommendations': recs_page,
        'total_recommendations': len(recommendations),
    }
    return render(request, 'jobs/recommended_jobs.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def application_detail(request, pk):
    """View a single job application."""
    application = get_object_or_404(
        JobApplication.objects.select_related('job', 'job__company'),
        pk=pk,
        user=request.user,
    )

    context = {
        'application': application,
        'job': application.job,
    }
    return render(request, 'jobs/application_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def unsave_job(request, pk):
    """Remove a saved job."""
    saved_job = get_object_or_404(SavedJob, user=request.user, job_id=pk)
    job_title = saved_job.job.title
    saved_job.delete()
    messages.success(request, f'Removed "{job_title}" from saved jobs.')
    return redirect('job_detail', pk=pk)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def create_job_alert(request):
    """Create a new job alert."""
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, f'Created job alert "{alert.title}".')
            return redirect('my_job_alerts')
    else:
        form = JobAlertForm()

    return render(request, 'jobs/create_job_alert.html', {'form': form})


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_job_alerts(request):
    """List the current user's job alerts."""
    alerts = JobAlert.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'jobs/my_job_alerts.html', {'alerts': alerts})


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_job_alert(request, pk):
    """Delete one of the user's job alerts."""
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    title = alert.title
    alert.delete()
    messages.success(request, f'Deleted job alert "{title}".')
    return redirect('my_job_alerts')


@require_http_methods(["GET"])
def companies(request):
    """Browse companies."""
    companies_qs = Company.objects.all().order_by('name')
    search = request.GET.get('search', '').strip()

    if search:
        companies_qs = companies_qs.filter(
            Q(name__icontains=search) |
            Q(industry__icontains=search) |
            Q(location__icontains=search)
        )

    paginator = Paginator(companies_qs, 9)
    page_number = request.GET.get('page')
    companies_page = paginator.get_page(page_number)

    context = {
        'companies': companies_page,
        'total_companies': companies_qs.count(),
    }
    return render(request, 'jobs/companies.html', context)


@require_http_methods(["GET"])
def company_detail(request, pk):
    """Show a company profile and its active jobs."""
    company = get_object_or_404(Company, pk=pk)
    jobs = Job.objects.filter(company=company, status='active').order_by('-posted_date')

    context = {
        'company': company,
        'jobs': jobs,
        'total_jobs': jobs.count(),
    }
    return render(request, 'jobs/company_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def auto_apply_settings(request):
    """Manage auto-apply permissions and queue state."""
    permission, _ = AutoApplyPermission.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        permission.allowed = request.POST.get('allowed') == 'on'
        permission.require_approval = request.POST.get('require_approval') == 'on'
        permission.terms_accepted = request.POST.get('terms_accepted') == 'on'

        try:
            permission.daily_limit = max(1, min(50, int(request.POST.get('daily_limit', permission.daily_limit))))
        except (TypeError, ValueError):
            messages.error(request, 'Please enter a valid daily limit.')
        else:
            permission.save()
            messages.success(request, 'Auto-apply settings saved.')

    queue_items = ApplicationQueue.objects.filter(
        user=request.user,
        status='pending',
    ).select_related('job', 'job__company').order_by('-queued_at')

    history_qs = ApplicationQueue.objects.filter(
        user=request.user,
    ).select_related('job', 'job__company').order_by('-queued_at')

    paginator = Paginator(history_qs, 10)
    page_number = request.GET.get('page')
    history = paginator.get_page(page_number)

    today = timezone.now().date()
    applied_today = ApplicationQueue.objects.filter(
        user=request.user,
        status='submitted',
        applied_at__date=today,
    ).count()

    context = {
        'permission': permission,
        'queue_items': queue_items,
        'history': history,
        'applied_today': applied_today,
        'pending_count': queue_items.count(),
        'total_applied': ApplicationQueue.objects.filter(user=request.user, status='submitted').count(),
    }
    return render(request, 'jobs/auto_apply.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def run_apply(request):
    """Run the auto-apply workflow for the current user."""
    result = run_auto_apply(request.user)
    status = result.get('status')
    results = result.get('results') or {}

    if not isinstance(results, dict):
        results = {}

    if status == 'done':
        messages.success(
            request,
            f"Auto-apply finished: {results.get('submitted', 0)} submitted, "
            f"{results.get('failed', 0)} failed."
        )
    elif status == 'disabled':
        messages.warning(request, result.get('message', 'Auto-apply is disabled.'))
    elif status == 'terms_required':
        messages.warning(request, result.get('message', 'Accept the terms first.'))
    elif status == 'limit_reached':
        messages.warning(request, result.get('message', 'Daily limit reached.'))
    else:
        messages.info(request, result.get('message', 'Auto-apply completed.'))

    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def approve_job(request, pk):
    """Approve a queued auto-apply job."""
    queue_item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    queue_item.status = 'approved'
    queue_item.save(update_fields=['status'])
    messages.success(request, f'Approved "{queue_item.job.title}" for auto-apply.')
    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def reject_job(request, pk):
    """Reject a queued auto-apply job."""
    queue_item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    queue_item.status = 'rejected'
    queue_item.save(update_fields=['status'])
    messages.info(request, f'Rejected "{queue_item.job.title}".')
    return redirect('auto_apply_settings')
