from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import (
    Post, Reply, Like, Category, UserProfile,
    Badge, UserBadge, MentorshipRequest, Notification
)
from .forms import (
    PostForm, ReplyForm, ProfileForm,
    MentorshipRequestForm, RegisterForm
)


# ─────────────────────────────────────────────
#  AUTH VIEWS
# ─────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect("community:home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to CareerAI Community, {user.username}! 🎉")
        return redirect("community:home")

    return render(request, "community/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("community:home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next", "community:home")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "community/login.html")


def logout_view(request):
    logout(request)
    return redirect("community:login")


# ─────────────────────────────────────────────
#  HOME VIEW
# ─────────────────────────────────────────────

@login_required
def home(request):
    """
    Lists posts with filters: category, sort order (trending/newest/unanswered).
    Sidebar: top 5 leaderboard + all categories.
    """
    category_slug = request.GET.get("category", "")
    sort = request.GET.get("sort", "newest")

    posts = Post.objects.filter(is_hidden=False).select_related(
    "author", "author__community_profile", "category"
)

    # Category filter
    active_category = None
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=active_category)

    # Sort order
    if sort == "trending":
        # Annotate with like + reply counts for sorting
        posts = posts.annotate(
            total_likes=Count("likes", filter=Q(likes__is_active=True)),
            total_replies=Count("replies")
        ).order_by("-is_pinned", "-total_likes", "-total_replies", "-created_at")
    elif sort == "unanswered":
        posts = posts.annotate(
            total_replies=Count("replies")
        ).filter(total_replies=0).order_by("-is_pinned", "-created_at")
    else:  # newest (default)
        posts = posts.order_by("-is_pinned", "-created_at")

    # Sidebar data
    categories = Category.objects.all().order_by("name")
    top_users = UserProfile.objects.select_related("user").order_by("-points")[:5]

    context = {
        "posts": posts,
        "categories": categories,
        "active_category": active_category,
        "sort": sort,
        "top_users": top_users,
    }
    return render(request, "community/home.html", context)


# ─────────────────────────────────────────────
#  POST DETAIL VIEW
# ─────────────────────────────────────────────

@login_required
def post_detail(request, pk):
    """
    Shows full post + threaded replies.
    Handles reply form submission.
    Increments view count once per session.
    """
    post = get_object_or_404(
        Post.objects.select_related("author", "author__community_profile", "category"),
        pk=pk,
        is_hidden=False,
    )

    # Increment view count once per session
    viewed_key = f"viewed_post_{pk}"
    if not request.session.get(viewed_key):
        Post.objects.filter(pk=pk).update(views=post.views + 1)
        request.session[viewed_key] = True

    # Top-level replies only (parent=None); nested replies fetched in template
    replies = Reply.objects.filter(
        post=post, parent=None, is_hidden=False
    ).select_related('author', 'author__community_profile', 'post')


    # Check if current user has liked this post
    user_liked_post = Like.objects.filter(
        user=request.user, post=post, is_active=True
    ).exists()

    # IDs of replies the user has liked
    user_liked_reply_ids = set(
        Like.objects.filter(
            user=request.user, reply__in=Reply.objects.filter(post=post), is_active=True
        ).values_list("reply_id", flat=True)
    )

    # Mentorship request form (only shown if post author is senior/employer)
    mentorship_form = None
    can_request_mentorship = False
    try:
        author_profile = post.author.community_profile
        if (
            author_profile.role in ("senior", "employer", "mentor")
            and request.user != post.author
        ):
            can_request_mentorship = True
            # Check if request already sent
            already_requested = MentorshipRequest.objects.filter(
                from_user=request.user,
                to_user=post.author,
            ).exists()
            if not already_requested:
                mentorship_form = MentorshipRequestForm()
    except UserProfile.DoesNotExist:
        pass

    # Reply form
    reply_form = ReplyForm()

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Submit a new reply ──
        if action == "reply":
            reply_form = ReplyForm(request.POST)
            if reply_form.is_valid():
                reply = reply_form.save(commit=False)
                reply.post = post
                reply.author = request.user
                parent_id = request.POST.get("parent_id")
                if parent_id:
                    try:
                        reply.parent = Reply.objects.get(pk=parent_id, post=post)
                    except Reply.DoesNotExist:
                        pass
                reply.save()  # signal fires here
                messages.success(request, "Reply posted! You earned 5 points. 🎉")
                return redirect("community:post_detail", pk=pk)

        # ── Send mentorship request ──
        elif action == "mentorship":
            mentorship_form = MentorshipRequestForm(request.POST)
            if mentorship_form.is_valid():
                already = MentorshipRequest.objects.filter(
                    from_user=request.user, to_user=post.author
                ).exists()
                if already:
                    messages.warning(request, "You've already sent a mentorship request to this user.")
                else:
                    mr = mentorship_form.save(commit=False)
                    mr.from_user = request.user
                    mr.to_user = post.author
                    mr.save()
                    Notification.objects.create(
                        user=post.author,
                        message=f"🤝 {request.user.username} sent you a mentorship request.",
                        link="/community/profile/",
                    )
                    messages.success(request, "Mentorship request sent!")
                return redirect("community:post_detail", pk=pk)

    context = {
        "post": post,
        "replies": replies,
        "reply_form": reply_form,
        "user_liked_post": user_liked_post,
        "user_liked_reply_ids": user_liked_reply_ids,
        "mentorship_form": mentorship_form,
        "can_request_mentorship": can_request_mentorship,
    }
    return render(request, "community/post_detail.html", context)


# ─────────────────────────────────────────────
#  CREATE POST VIEW
# ─────────────────────────────────────────────

@login_required
def create_post(request):
    """Create a new post. Signal awards 10 points on save."""
    form = PostForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()  # signal fires here
        messages.success(request, f"Post published! You earned 10 points. ✅")
        return redirect("community:post_detail", pk=post.pk)

    return render(request, "community/create_post.html", {"form": form})


# ─────────────────────────────────────────────
#  LIKE TOGGLE VIEW  (AJAX-friendly)
# ─────────────────────────────────────────────

@login_required
@require_POST
def like_toggle(request):
    """
    Toggles a like on a post or reply.
    Returns JSON so the template can update the count without reload.
    """
    post_id = request.POST.get("post_id")
    reply_id = request.POST.get("reply_id")

    if not post_id and not reply_id:
        return JsonResponse({"error": "No target specified."}, status=400)

    # Determine target object and owner
    if post_id:
        target_post = get_object_or_404(Post, pk=post_id, is_hidden=False)
        target_reply = None
        owner = target_post.author
    else:
        target_reply = get_object_or_404(Reply, pk=reply_id, is_hidden=False)
        target_post = None
        owner = target_reply.author

    # Business rule: cannot like own content
    if owner == request.user:
        return JsonResponse({"error": "You cannot like your own content."}, status=403)

    # Get or create the Like row
    like, created = Like.objects.get_or_create(
        user=request.user,
        post=target_post,
        reply=target_reply,
    )

    if created:
        like.is_active = True
    else:
        like.is_active = not like.is_active  # toggle

    like.save()  # signal fires here

    # Return updated like count
    if target_post:
        count = target_post.like_count()
    else:
        count = target_reply.like_count()

    return JsonResponse({
        "liked": like.is_active,
        "count": count,
    })


# ─────────────────────────────────────────────
#  LEADERBOARD VIEW
# ─────────────────────────────────────────────

@login_required
def leaderboard(request):
    """Top users ranked by points with badges."""
    top_users = UserProfile.objects.select_related("user").order_by("-points")[:50]

    # Attach badge count to each profile
    user_ids = [p.user_id for p in top_users]
    badge_counts = (
        UserBadge.objects.filter(user_id__in=user_ids)
        .values("user_id")
        .annotate(count=Count("id"))
    )
    badge_map = {row["user_id"]: row["count"] for row in badge_counts}

    for profile in top_users:
        profile.badge_count = badge_map.get(profile.user_id, 0)

    # Current user's rank
    current_user_rank = None
    try:
        current_points = request.user.community_profile.points
        current_user_rank = UserProfile.objects.filter(
            points__gt=current_points
        ).count() + 1
    except UserProfile.DoesNotExist:
        pass

    context = {
        "top_users": top_users,
        "current_user_rank": current_user_rank,
    }
    return render(request, "community/leaderboard.html", context)


# ─────────────────────────────────────────────
#  USER PROFILE VIEW
# ─────────────────────────────────────────────

@login_required
def user_profile(request, username=None):
    """
    Shows a user's public profile.
    If username is None, shows the logged-in user's own profile.
    """
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = request.user

    profile = get_object_or_404(UserProfile, user=profile_user)

    user_posts = Post.objects.filter(
        author=profile_user, is_hidden=False
    ).order_by("-created_at")[:10]

    earned_badges = UserBadge.objects.filter(
        user=profile_user
    ).select_related("badge").order_by("earned_at")

    # Mentorship requests — shown only on own profile
    sent_requests = received_requests = None
    if profile_user == request.user:
        sent_requests = MentorshipRequest.objects.filter(
            from_user=request.user
        ).select_related("to_user", "to_user__community_profile").order_by("-created_at")

        received_requests = MentorshipRequest.objects.filter(
            to_user=request.user
        ).select_related("from_user", "from_user__community_profile").order_by("-created_at")

    context = {
        "profile_user": profile_user,
        "profile": profile,
        "user_posts": user_posts,
        "earned_badges": earned_badges,
        "sent_requests": sent_requests,
        "received_requests": received_requests,
        "is_own_profile": profile_user == request.user,
    }
    return render(request, "community/profile.html", context)


# ─────────────────────────────────────────────
#  EDIT PROFILE VIEW
# ─────────────────────────────────────────────

@login_required
def edit_profile(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    form = ProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully! ✅")
        return redirect("community:user_profile", username=request.user.username)

    return render(request, "community/edit_profile.html", {
        "form": form,
        "profile": profile,
    })

# ─────────────────────────────────────────────
#  MENTORSHIP MANAGE VIEW
# ─────────────────────────────────────────────

@login_required
@require_POST
def mentorship_manage(request):
    """Accept or decline a mentorship request. Only the recipient can act."""
    request_id = request.POST.get("request_id")
    action = request.POST.get("action")  # "accept" or "decline"

    mr = get_object_or_404(MentorshipRequest, pk=request_id, to_user=request.user)

    if action == "accept":
        mr.status = "accepted"
        mr.save()
        Notification.objects.create(
            user=mr.from_user,
            message=f"✅ {request.user.username} accepted your mentorship request!",
            link=f"/community/profile/{request.user.username}/",
        )
        messages.success(request, f"You accepted {mr.from_user.username}'s mentorship request.")
    elif action == "decline":
        mr.status = "declined"
        mr.save()
        Notification.objects.create(
            user=mr.from_user,
            message=f"❌ {request.user.username} declined your mentorship request.",
            link="/community/profile/",
        )
        messages.info(request, f"Request from {mr.from_user.username} declined.")
    else:
        messages.error(request, "Invalid action.")

    return redirect("community:user_profile")


# ─────────────────────────────────────────────
#  SEARCH VIEW
# ─────────────────────────────────────────────

@login_required
def search(request):
    """Search posts by title, body, or category name."""
    query = request.GET.get("q", "").strip()
    results = []

    if query:
        results = Post.objects.filter(
            is_hidden=False
        ).filter(
            Q(title__icontains=query) |
            Q(body__icontains=query) |
            Q(category__name__icontains=query)
        ).select_related(
            "author", "author__community_profile", "category"
        ).order_by("-created_at")

    context = {
        "query": query,
        "results": results,
        "result_count": len(results) if query else 0,
    }
    return render(request, "community/search.html", context)


# ─────────────────────────────────────────────
#  NOTIFICATIONS VIEW
# ─────────────────────────────────────────────
@login_required
def notifications_view(request):
    if request.method == 'POST' and request.POST.get('mark_all_read'):
        Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return redirect('community:notifications')

    # Auto-mark all as read on page load
    Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    return render(request, 'community/notifications.html', {
        'notifications': notifications,
        'unread_count':  unread_count,
    })
