from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Resource, Bookmark, UserProgress, CVSkillGap


def resource_hub(request):
    resources = Resource.objects.all()
    categories = Resource.CATEGORY_CHOICES
    context = {
        'resources': resources,
        'categories': categories,
    }
    return render(request, 'resource_hub/resource_hub.html', context)


def browse_resources(request):
    resources = Resource.objects.all()
    category = request.GET.get('category')
    level = request.GET.get('level')
    resource_type = request.GET.get('resource_type')
    search = request.GET.get('search')
    is_free = request.GET.get('is_free')

    if category:
        resources = resources.filter(category=category)
    if level:
        resources = resources.filter(level=level)
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    if search:
        resources = resources.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(tags__icontains=search)
        )
    if is_free:
        resources = resources.filter(is_free=True)

    context = {
        'resources': resources,
        'categories': Resource.CATEGORY_CHOICES,
        'levels': Resource.LEVEL_CHOICES,
        'types': Resource.RESOURCE_TYPE_CHOICES,
        'selected_category': category,
        'selected_level': level,
        'search': search,
    }
    return render(request, 'resource_hub/browse_resources.html', context)


def resource_detail(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    resource.view_count += 1
    resource.save(update_fields=['view_count'])

    is_bookmarked = False
    user_progress = None
    if request.user.is_authenticated:
        is_bookmarked = Bookmark.objects.filter(user=request.user, resource=resource).exists()
        user_progress, _ = UserProgress.objects.get_or_create(user=request.user, resource=resource)

    related = Resource.objects.filter(category=resource.category).exclude(pk=pk)[:4]

    context = {
        'resource': resource,
        'is_bookmarked': is_bookmarked,
        'user_progress': user_progress,
        'related': related,
    }
    return render(request, 'resource_hub/resource_detail.html', context)


@login_required(login_url='login')
def toggle_bookmark(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, resource=resource)
    if not created:
        bookmark.delete()
    return redirect('resource_detail', pk=pk)


@login_required(login_url='login')
def my_learning(request):
    progress = UserProgress.objects.filter(user=request.user).select_related('resource')
    bookmarks = Bookmark.objects.filter(user=request.user).select_related('resource')
    context = {
        'progress': progress,
        'bookmarks': bookmarks,
    }
    return render(request, 'resource_hub/my_learning.html', context)


@login_required(login_url='login')
def update_progress(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    progress, _ = UserProgress.objects.get_or_create(user=request.user, resource=resource)
    status = request.POST.get('status')
    if status in ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED']:
        progress.status = status
        progress.save()
    return redirect('resource_detail', pk=pk)