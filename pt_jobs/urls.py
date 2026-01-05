# pt_jobs/urls.py
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views

from django.conf import settings
from django.conf.urls.static import static

from board import views as board_views

# 🔍 DEBUG endpoint (temporary, safe, browser-checkable)
from pt_jobs.debug_views import debug_status


urlpatterns = [
    # ✅ Must be BEFORE "admin/" or Django admin catch-all will swallow it
    path("admin/dashboard/", board_views.admin_dashboard, name="admin_dashboard"),

    # Django admin
    path("admin/", admin.site.urls),

    # 🔍 DEBUG – proves which templates + code are deployed on Railway
    path("__debug__/status/", debug_status, name="debug_status"),

    # Main app
    path("", include("board.urls")),

    # Password reset (templates live in templates/auth/)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]

# Serve uploaded media in development so logos/hero images render
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


