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

# Import Streamlit scraper modules
try:
    from scraper.orchestrator import ScraperOrchestrator
    from analyzer.skills import get_skill_extractor
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    import logging
    logging.warning("Scraper modules not available. Job search with scraper will be disabled.")

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def job_list(request):
    """List all jobs with search, filter, and sort"""
    jobs = Job.objects.filter(status='active')
    
    form = JobSearchForm(request.GET)
    
    if form.is_valid():
        # Keyword search
        keyword = form.cleaned_data.get('keyword')
        if keyword:
            jobs = jobs.filter(
                Q(title__icontains=keyword) |
                Q(description__icontains=keyword) |
                Q(required_skills__icontains=keyword)
            )
        
        # Location filter
        location = form.cleaned_data.get('location')
        if location:
            jobs = jobs.filter(location__icontains=location)
        
        # Job type filter
        job_types = form.cleaned_data.get('job_type')
        if job_types:
            jobs = jobs.filter(job_type__in=job_types)
        
        # Experience level filter
        exp_levels = form.cleaned_data.get('experience_level')
        if exp_levels:
            jobs = jobs.filter(experience_level__in=exp_levels)
        
        # Salary range filter
        salary_min = form.cleaned_data.get('salary_min')
        salary_max = form.cleaned_data.get('salary_max')
        
        if salary_min:
            jobs = jobs.filter(Q(salary_min__gte=salary_min) | Q(salary_min__isnull=True))
        if salary_max:
            jobs = jobs.filter(Q(salary_max__lte=salary_max) | Q(salary_max__isnull=True))
        
        # Sorting
        sort_by = form.cleaned_data.get('sort_by')
        if sort_by == 'newest':
            jobs = jobs.order_by('-posted_date')
        elif sort_by == 'salary_high':
            jobs = jobs.order_by('-salary_max')
        elif sort_by == 'salary_low':
            jobs = jobs.order_by('salary_min')
    
    # Pagination
    paginator = Paginator(jobs, 10)
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'jobs': jobs_page,
        'total_jobs': paginator.count,
    }
    return render(request, 'jobs/job_list.html', context)


@require_http_methods(["GET"])
def job_detail(request, pk):
    """View job details with match score"""
    job = get_object_or_404(Job, pk=pk)
    
    # Increment views
    job.views_count += 1
    job.save(update_fields=['views_count'])
    
    # Check if user has applied
    user_applied = False
    if request.user.is_authenticated:
        user_applied = JobApplication.objects.filter(user=request.user, job=job).exists()
    
    # Check if job is saved
    job_saved = False
    if request.user.is_authenticated:
        job_saved = SavedJob.objects.filter(user=request.user, job=job).exists()
    
    # Get job match score (if user has analyzed their CV)
    match_score = None
    if request.user.is_authenticated:
        match_score = JobMatchScore.objects.filter(user=request.user, job=job).first()
    
    context = {
        'job': job,
        'user_applied': user_applied,
        'job_saved': job_saved,
        'match_score': match_score,
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def apply_job(request, pk):
    """Apply for a job"""
    job = get_object_or_404(Job, pk=pk)
    
    # Check if already applied
    existing_application = JobApplication.objects.filter(user=request.user, job=job).first()
    
    if existing_application:
        messages.warning(request, 'You have already applied for this job.')
        return redirect('job_detail', pk=job.pk)
    
    if request.method == 'POST':
        form = JobApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.job = job
            application.save()
            
            # Update applicants count
            job.applicants_count += 1
            job.save(update_fields=['applicants_count'])
            
            messages.success(request, 'Application submitted successfully!')
            return redirect('job_detail', pk=job.pk)
    else:
        form = JobApplicationForm()
    
    context = {
        'form': form,
        'job': job,
    }
    return render(request, 'jobs/apply_job.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def save_job(request, pk):
    """Save a job"""
    job = get_object_or_404(Job, pk=pk)
    
    saved_job, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    
    if created:
        messages.success(request, 'Job saved successfully!')
    else:
        messages.info(request, 'Job is already saved.')
    
    return redirect('job_detail', pk=job.pk)


@login_required(login_url='login')
@require_http_methods(["POST"])
def unsave_job(request, pk):
    """Unsave a job"""
    job = get_object_or_404(Job, pk=pk)
    
    SavedJob.objects.filter(user=request.user, job=job).delete()
    messages.success(request, 'Job removed from saved.')
    
    return redirect('job_detail', pk=job.pk)


@login_required(login_url='login')
@require_http_methods(["GET"])
def saved_jobs(request):
    """View saved jobs"""
    saved_jobs_qs = SavedJob.objects.filter(user=request.user).select_related('job')
    
    # Pagination
    paginator = Paginator(saved_jobs_qs, 10)
    page_number = request.GET.get('page')
    saved_jobs_page = paginator.get_page(page_number)
    
    context = {
        'saved_jobs': saved_jobs_page,
        'total_saved': paginator.count,
    }
    return render(request, 'jobs/saved_jobs.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_applications(request):
    """View user's job applications"""
    applications = JobApplication.objects.filter(user=request.user).select_related('job', 'job__company')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        applications = applications.filter(status=status)
    
    # Pagination
    paginator = Paginator(applications, 10)
    page_number = request.GET.get('page')
    applications_page = paginator.get_page(page_number)
    
    context = {
        'applications': applications_page,
        'total_applications': paginator.count,
        'status_filter': status,
        'status_choices': JobApplication._meta.get_field('status').choices,
    }
    return render(request, 'jobs/my_applications.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def application_detail(request, pk):
    """View application details"""
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    
    context = {
        'application': application,
        'job': application.job,
    }
    return render(request, 'jobs/application_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def create_job_alert(request):
    """Create job alert"""
    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, 'Job alert created successfully!')
            return redirect('my_job_alerts')
    else:
        form = JobAlertForm()
    
    context = {
        'form': form,
    }
    return render(request, 'jobs/create_job_alert.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def my_job_alerts(request):
    """View user's job alerts"""
    alerts = JobAlert.objects.filter(user=request.user)
    
    context = {
        'alerts': alerts,
        'total_alerts': alerts.count(),
    }
    return render(request, 'jobs/my_job_alerts.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_job_alert(request, pk):
    """Delete job alert"""
    alert = get_object_or_404(JobAlert, pk=pk, user=request.user)
    alert.delete()
    messages.success(request, 'Job alert deleted.')
    return redirect('my_job_alerts')


@require_http_methods(["GET"])
def companies(request):
    """List all companies"""
    companies_qs = Company.objects.all()
    
    # Search
    search = request.GET.get('search')
    if search:
        companies_qs = companies_qs.filter(
            Q(name__icontains=search) |
            Q(industry__icontains=search) |
            Q(location__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(companies_qs, 12)
    page_number = request.GET.get('page')
    companies_page = paginator.get_page(page_number)
    
    context = {
        'companies': companies_page,
        'total_companies': paginator.count,
        'search_query': search,
    }
    return render(request, 'jobs/companies.html', context)


@require_http_methods(["GET"])
def company_detail(request, pk):
    """View company details and their jobs"""
    company = get_object_or_404(Company, pk=pk)
    jobs = Job.objects.filter(company=company, status='active')
    
    context = {
        'company': company,
        'jobs': jobs,
        'total_jobs': jobs.count(),
    }
    return render(request, 'jobs/company_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def recommended_jobs(request):
    """Get recommended jobs based on user CV analysis"""
    try:
        # Get user's latest CV analysis
        from cv_analyzer.models import CVAnalysis
        cv_analysis = CVAnalysis.objects.filter(
            user=request.user, 
            is_analyzed=True
        ).latest('created_at')
        
        # Parse extracted skills
        skills = json.loads(cv_analysis.extracted_skills) if cv_analysis.extracted_skills else {'technical': [], 'soft': []}
        user_technical_skills = skills.get('technical', [])
    except:
        messages.info(request, 'Analyze your CV first for personalized job recommendations.')
        return redirect('upload_cv_analysis')
    
    if not user_technical_skills:
        messages.warning(request, 'No skills detected in your CV. Add skills for better recommendations.')
        return redirect('cv_analysis_detail', pk=cv_analysis.pk)
    
    # Filter jobs by skill match
    jobs = Job.objects.filter(status='active')
    
    # Calculate match scores
    jobs_with_scores = []
    for job in jobs:
        job_skills = set(s.lower() for s in job.get_required_skills_list())
        user_skills_set = set(s.lower() for s in user_technical_skills)
        
        if job_skills:
            match_count = len(job_skills & user_skills_set)
            match_percentage = int((match_count / len(job_skills)) * 100)
        else:
            match_percentage = 0
        
        job.match_percentage = match_percentage
        jobs_with_scores.append(job)
    
    # Sort by match percentage
    jobs_with_scores = sorted(jobs_with_scores, key=lambda x: x.match_percentage, reverse=True)
    
    # Pagination
    paginator = Paginator(jobs_with_scores, 10)
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)
    
    context = {
        'jobs': jobs_page,
        'total_jobs': len(jobs_with_scores),
        'user_skills_count': len(user_technical_skills),
    }
    return render(request, 'jobs/recommended_jobs.html', context)


# ─── NEW: Job Scraper & Smart Matching (Streamlit Integration) ────────────

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def job_search_with_scraper(request):
    """
    Search jobs using Streamlit scraper with smart CV matching
    
    ✅ NEW FEATURE (v2.1):
    - Uses scraper.orchestrator to search multiple portals
    - Integrates with CV analysis for personalized matching
    - Supports demo mode (mock data) or live scraping
    - Displays match scores for each job
    """
    
    if not SCRAPER_AVAILABLE:
        messages.error(request, '❌ Scraper modules not installed. Please install required packages.')
        return redirect('job_list')
    
    # Check if user has analyzed their CV
    try:
        from cv_analyzer.models import CVAnalysis
        cv_analysis = CVAnalysis.objects.filter(
            user=request.user,
            is_analyzed=True
        ).latest('created_at')
        
        cv_skills = json.loads(cv_analysis.extracted_skills) if cv_analysis.extracted_skills else {'technical': [], 'soft': []}
        has_cv_analysis = True
        user_skills = cv_skills.get('technical', [])[:5]
    except:
        has_cv_analysis = False
        cv_analysis = None
        user_skills = []
    
    if not has_cv_analysis:
        messages.warning(request, '⚠️ No CV analyzed yet. Analyze your CV for personalized job matching.')
    
    scraped_jobs = []
    search_performed = False
    demo_mode = True
    
    if request.method == 'GET':
        query = request.GET.get('q', '')
        location = request.GET.get('location', '')
        demo_mode = request.GET.get('demo', 'true').lower() == 'true'
        
        if query:
            search_performed = True
            try:
                logger.info(f"Scraper search: query={query}, location={location}, demo={demo_mode}")
                
                # Initialize orchestrator with skill database
                skill_db = None
                if has_cv_analysis:
                    try:
                        skill_extractor = get_skill_extractor()
                        skill_db = skill_extractor.skill_db
                    except Exception as e:
                        logger.warning(f"Could not load skill database: {e}")
                
                orchestrator = ScraperOrchestrator(skill_db=skill_db)
                
                # Run scraper
                try:
                    scraped_jobs = orchestrator.run(
                        query=query,
                        location=location or None,
                        portals=['LinkedIn', 'Indeed', 'Rozee.pk'],
                        user_skills=cv_skills if has_cv_analysis else {},
                        max_per_portal=8,
                        demo_mode=demo_mode,
                        force_refresh=request.GET.get('refresh') == 'true'
                    )
                    
                    # Store scraped jobs in Django database
                    for job_data in scraped_jobs:
                        try:
                            company, _ = Company.objects.get_or_create(
                                name=job_data.company,
                                defaults={
                                    'location': job_data.location or 'Not specified',
                                    'industry': 'Technology',
                                }
                            )
                            
                            job, created = Job.objects.get_or_create(
                                title=job_data.title,
                                company=company,
                                location=job_data.location,
                                defaults={
                                    'description': job_data.description or '',
                                    'job_type': 'full-time',
                                    'experience_level': 'mid',
                                    'required_skills': ','.join(job_data.skills_mentioned)[:500],
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
                        except Exception as e:
                            logger.error(f"Error storing scraped job: {e}")
                            continue
                    
                    messages.success(
                        request,
                        f'✅ Found {len(scraped_jobs)} jobs! '
                        + ('Matched against your CV.' if has_cv_analysis else 'Analyze your CV for personalized matching.')
                    )
                
                except Exception as scraper_error:
                    logger.exception(f"Scraper orchestrator error: {scraper_error}")
                    messages.error(request, f'Scraper error: {str(scraper_error)}')
                    scraped_jobs = []
            
            except Exception as e:
                logger.exception(f"Job search error: {e}")
                messages.error(request, f'Search failed: {str(e)}')
    
    # Pagination
    paginator = Paginator(scraped_jobs, 15)
    page_number = request.GET.get('page', 1)
    jobs_page = paginator.get_page(page_number)
    
    context = {
        'jobs': jobs_page,
        'total_jobs': len(scraped_jobs),
        'search_performed': search_performed,
        'has_cv_analysis': has_cv_analysis,
        'user_skills': user_skills,
        'demo_mode': demo_mode,
    }
    return render(request, 'jobs/job_search_with_scraper.html', context)


# ─── Auto-Apply Agent Views ────────────────────────────────────────────

def _get_or_create_permission(user):
    """Helper function to get or create auto-apply permission"""
    permission, _ = AutoApplyPermission.objects.get_or_create(user=user)
    return permission


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def auto_apply_settings(request):
    """Main Auto-Apply control panel with unified UI"""
    permission = _get_or_create_permission(request.user)

    if request.method == 'POST':
        terms_accepted = request.POST.get('terms_accepted') == 'on'
        allowed = request.POST.get('allowed') == 'on'
        require_approval = request.POST.get('require_approval') == 'on'

        try:
            daily_limit = int(request.POST.get('daily_limit', 10))
            daily_limit = max(1, min(50, daily_limit))
        except (ValueError, TypeError):
            daily_limit = 10

        if allowed and not terms_accepted:
            messages.error(request, 'You must accept the terms to enable Auto-Apply.')
            return redirect('auto_apply_settings')

        permission.terms_accepted = terms_accepted
        permission.allowed = allowed
        permission.require_approval = require_approval
        permission.daily_limit = daily_limit
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

    # Stats
    today = timezone.now().date()
    applied_today = ApplicationQueue.objects.filter(
        user=request.user, status='submitted', applied_at__date=today
    ).count()
    pending_count = ApplicationQueue.objects.filter(user=request.user, status='pending').count()
    total_applied = ApplicationQueue.objects.filter(user=request.user, status='submitted').count()

    # Approval queue
    queue_items = (
        ApplicationQueue.objects
        .filter(user=request.user, status='pending')
        .select_related('job', 'job__company')
        .order_by('-match_score')
    )

    # Application history (paginated)
    history_qs = (
        ApplicationQueue.objects
        .filter(user=request.user, status__in=['submitted', 'failed', 'rejected'])
        .select_related('job', 'job__company')
    )
    paginator = Paginator(history_qs, 20)
    history = paginator.get_page(request.GET.get('page'))

    context = {
        'permission': permission,
        'applied_today': applied_today,
        'pending_count': pending_count,
        'total_applied': total_applied,
        'queue_items': queue_items,
        'history': history,
    }
    return render(request, 'jobs/auto_apply.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def approve_job(request, pk):
    """Approve a queued job for auto-application"""
    item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    if item.status == 'pending':
        item.status = 'approved'
        item.save()
        AuditLog.objects.create(
            user=request.user,
            job=item.job,
            action='job_approved',
            status='approved',
            detail=f'Approved: {item.job.title}',
        )
        messages.success(request, f'✅ "{item.job.title}" approved for auto-apply.')
    return redirect('auto_apply_settings')


@login_required(login_url='login')
@require_http_methods(["POST"])
def reject_job(request, pk):
    """Reject a queued job"""
    item = get_object_or_404(ApplicationQueue, pk=pk, user=request.user)
    if item.status in ('pending', 'approved'):
        item.status = 'rejected'
        item.save()
        AuditLog.objects.create(
            user=request.user,
            job=item.job,
            action='job_rejected',
            status='rejected',
            detail=f'Rejected: {item.job.title}',
        )
        messages.info(request, f'"{item.job.title}" rejected.')
    return redirect('auto_apply_settings')