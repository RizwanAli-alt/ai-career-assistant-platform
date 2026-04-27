from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    # ── Auth ──────────────────────────────────────────
    path("register/",               views.register_view,      name="register"),
    path("login/",                  views.login_view,          name="login"),
    path("logout/",                 views.logout_view,         name="logout"),

    # ── Core ──────────────────────────────────────────
    path("",                        views.home,                name="home"),
    path("post/create/",            views.create_post,         name="create_post"),
    path("post/<int:pk>/",          views.post_detail,         name="post_detail"),

    # ── Interactions ──────────────────────────────────
    path("like/",                   views.like_toggle,         name="like_toggle"),

    # ── Profiles ──────────────────────────────────────
    path("profile/",                views.user_profile,        name="user_profile"),
    path("profile/edit/",           views.edit_profile,        name="edit_profile"),
    path("profile/<str:username>/", views.user_profile,        name="user_profile_public"),

    # ── Mentorship ────────────────────────────────────
    path("mentorship/manage/",      views.mentorship_manage,   name="mentorship_manage"),

    # ── Discovery ─────────────────────────────────────
    path("leaderboard/",            views.leaderboard,         name="leaderboard"),
    path("search/",                 views.search,              name="search"),

    # ── Notifications ─────────────────────────────────
    path("notifications/",          views.notifications_view,  name="notifications"),
]