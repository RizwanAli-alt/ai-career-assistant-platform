from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta
import json

from jobs.models import (
    JobApplication,
    SavedJob,
    ApplicationQueue,
    AutoApplyPermission,
)
from cv_analyzer.models import CVAnalysis
from forum.models import Post
from .models import UserActivity, UserStats, GoalTracker

CV_ANALYSES_MONTHLY_GOAL = 4


@login_required(login_url='login')
@require_http_methods(["GET"])
def dashboard(request):
    """Main dashboard"""
    user = request.user

    def normalize_text_list(value):
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            cleaned = value.replace('\n', ',')
            return [item.strip() for item in cleaned.split(',') if item.strip()]
        return []
    
    # Get or create user stats
    try:
        stats = UserStats.objects.get(user=user)
    except UserStats.DoesNotExist:
        stats = UserStats.objects.create(user=user)
    
    # Get recent activities
    activities = UserActivity.objects.filter(user=user)[:10]
    
    # Get stats
    recent_applications = JobApplication.objects.filter(user=user).count()
    saved_jobs = SavedJob.objects.filter(user=user).count()
    cv_analyses = CVAnalysis.objects.filter(user=user).count()
    forum_posts = Post.objects.filter(author=user).count()
    
    # Get this month's applications
    this_month_applications = JobApplication.objects.filter(
        user=user,
        applied_date__month=timezone.now().month
    ).count()
    
    # Get active goals
    active_goals = GoalTracker.objects.filter(user=user, status='active')

    # Latest CV analysis (for compact summary widget)
    latest_cv_analysis = CVAnalysis.objects.filter(user=user, is_analyzed=True).order_by('-created_at').first()
    cv_score = latest_cv_analysis.overall_score if latest_cv_analysis else 0
    cv_metrics = {
        'ats_compat': latest_cv_analysis.readability_score if latest_cv_analysis else 0,
        'keyword_match': latest_cv_analysis.keyword_score if latest_cv_analysis else 0,
        'completeness': latest_cv_analysis.content_score if latest_cv_analysis else 0,
        'formatting': latest_cv_analysis.format_score if latest_cv_analysis else 0,
    }
    cv_analyses_progress = (
        min(int((cv_analyses / CV_ANALYSES_MONTHLY_GOAL) * 100), 100)
        if cv_analyses and CV_ANALYSES_MONTHLY_GOAL > 0
        else 0
    )
    missing_skills = []
    if latest_cv_analysis:
        try:
            recommendations_data = json.loads(latest_cv_analysis.recommendations or '[]')
            if isinstance(recommendations_data, dict):
                missing_skills = normalize_text_list(
                    recommendations_data.get('missing_skills')
                    or recommendations_data.get('skills_gap')
                )
            elif isinstance(recommendations_data, list):
                missing_skills = normalize_text_list(recommendations_data)
        except (json.JSONDecodeError, TypeError):
            pass
        if not missing_skills:
            missing_skills = normalize_text_list(latest_cv_analysis.keyword_feedback)[:6]

    # Auto-apply status and quick stats
    auto_apply_allowed = False
    try:
        auto_apply_allowed = AutoApplyPermission.objects.get(user=user).allowed
    except AutoApplyPermission.DoesNotExist:
        auto_apply_allowed = False
    queue_items = ApplicationQueue.objects.filter(user=user).select_related('job__company')
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    auto_apply_today = queue_items.filter(
        status='submitted',
        queued_at__gte=start_of_day,
        queued_at__lt=end_of_day
    ).count()
    auto_apply_week = queue_items.filter(status='submitted', queued_at__gte=week_ago).count()
    auto_apply_total = queue_items.filter(status='submitted').count()
    recent_auto_apply = queue_items[:3]

    # Safe profile access
    try:
        profile = user.profile
    except (ObjectDoesNotExist, AttributeError):
        profile = None
    completion_items = [
        bool(profile and profile.bio),
        bool(user.email),
        bool(profile and profile.skills),
        bool(profile and profile.cv),
    ]
    profile_completion = int((sum(completion_items) / len(completion_items)) * 100) if completion_items else 0
    
    context = {
        'stats': stats,
        'activities': activities,
        'recent_applications': recent_applications,
        'saved_jobs': saved_jobs,
        'cv_analyses': cv_analyses,
        'forum_posts': forum_posts,
        'this_month_applications': this_month_applications,
        'active_goals': active_goals,
        'today_date': timezone.localtime(now).strftime('%B %d, %Y'),
        'latest_cv_analysis': latest_cv_analysis,
        'cv_score': cv_score,
        'cv_metrics': cv_metrics,
        'cv_analyses_progress': cv_analyses_progress,
        'missing_skills': missing_skills,
        'auto_apply_allowed': auto_apply_allowed,
        'auto_apply_today': auto_apply_today,
        'auto_apply_week': auto_apply_week,
        'auto_apply_total': auto_apply_total,
        'recent_auto_apply': recent_auto_apply,
        'profile': profile,
        'profile_completion': profile_completion,
        'cv_analyses_goal': CV_ANALYSES_MONTHLY_GOAL,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def analytics(request):
    """Analytics and insights"""
    user = request.user
    
    # Job applications over time
    last_30_days = timezone.now() - timedelta(days=30)
    applications_last_30 = JobApplication.objects.filter(
        user=user,
        applied_date__gte=last_30_days
    ).count()
    
    # Applications by status
    applications_by_status = JobApplication.objects.filter(user=user).values('status').annotate(count=Count('id'))
    
    # Most applied job types
    applied_jobs = JobApplication.objects.filter(user=user).select_related('job')
    job_type_stats = {}
    for app in applied_jobs:
        job_type = app.job.job_type
        job_type_stats[job_type] = job_type_stats.get(job_type, 0) + 1
    
    context = {
        'applications_last_30': applications_last_30,
        'applications_by_status': applications_by_status,
        'job_type_stats': job_type_stats,
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required(login_url='login')
@require_http_methods(["GET"])
def activity_log(request):
    """View activity log"""
    activities = UserActivity.objects.filter(user=request.user)
    
    # Filter by type if provided
    activity_type = request.GET.get('type')
    if activity_type:
        activities = activities.filter(activity_type=activity_type)
    
    context = {
        'activities': activities,
        'activity_type': activity_type,
    }
    return render(request, 'dashboard/activity_log.html', context)


@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def goal_tracker(request):
    """Manage career goals"""
    goals = GoalTracker.objects.filter(user=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        target_date = request.POST.get('target_date')
        
        if title and target_date:
            GoalTracker.objects.create(
                user=request.user,
                title=title,
                description=description,
                target_date=target_date
            )
            messages.success(request, 'Goal created successfully!')
            return redirect('goal_tracker')
    
    context = {
        'goals': goals,
    }
    return render(request, 'dashboard/goal_tracker.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_goal_progress(request, goal_id):
    """Update goal progress"""
    goal = get_object_or_404(GoalTracker, pk=goal_id, user=request.user)
    progress = request.POST.get('progress')
    
    if progress:
        goal.progress_percentage = int(progress)
        goal.save(update_fields=['progress_percentage'])
        messages.success(request, 'Goal progress updated!')
    
    return redirect('goal_tracker')


@login_required(login_url='login')
@require_http_methods(["POST"])
def delete_goal(request, goal_id):
    """Delete goal"""
    goal = get_object_or_404(GoalTracker, pk=goal_id, user=request.user)
    goal.delete()
    messages.success(request, 'Goal deleted.')
    return redirect('goal_tracker')


@login_required(login_url='login')
@require_http_methods(["GET"])
def recommendations(request):
    """Get personalized recommendations"""
    user = request.user
    recommendations = []
    
    # Check CV
    cv_analyses = CVAnalysis.objects.filter(user=user)
    if not cv_analyses.exists():
        recommendations.append({
            'type': 'cv_analysis',
            'title': 'Analyze Your CV',
            'description': 'Get AI-powered feedback to improve your resume',
            'priority': 'high',
            'icon': 'fa-file-pdf'
        })
    
    # Check profile completion
    if not user.profile.bio or not user.profile.skills:
        recommendations.append({
            'type': 'profile',
            'title': 'Complete Your Profile',
            'description': 'Add bio and skills to increase job match',
            'priority': 'high',
            'icon': 'fa-user'
        })
    
    # Check applications
    this_month_apps = JobApplication.objects.filter(
        user=user,
        applied_date__month=timezone.now().month
    ).count()
    
    if this_month_apps < 3:
        recommendations.append({
            'type': 'jobs',
            'title': 'Apply to More Jobs',
            'description': f'You\'ve applied to {this_month_apps} jobs this month',
            'priority': 'medium',
            'icon': 'fa-briefcase'
        })
    
    context = {
        'recommendations': recommendations,
    }
    return render(request, 'dashboard/recommendations.html', context)
