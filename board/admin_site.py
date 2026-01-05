# board/admin_site.py
from django.contrib import admin
from .models import SiteSettings, SiteEmailSettings  # use the originals already in board.models

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name", "admin_notify_email", "updated_at")
    fieldsets = (
        ("Branding", {"fields": ("site_name", "site_logo")}),
        ("General", {"fields": ("admin_notify_email", "default_from_email")}),
        ("Mapbox", {"fields": ("mapbox_token",)}),
        ("Email / SMTP (optional)", {
            "fields": (
                "email_host", "email_port", "email_host_user",
                "email_host_password", "email_use_tls", "email_use_ssl"
            ),
            "description": "Leave blank to fall back to environment variables / settings.py.",
        }),
    )

    def has_add_permission(self, request):
        # Keep it single-row if that's how you’ve been using it
        return not SiteSettings.objects.exists()


@admin.register(SiteEmailSettings)
class SiteEmailSettingsAdmin(admin.ModelAdmin):
    list_display = ("default_from_email", "admin_email", "send_application_copy_to_admin", "is_active")
    list_filter = ("is_active", "send_application_copy_to_admin")
    search_fields = ("default_from_email", "admin_email")
    fieldsets = (
        (None, {"fields": ("is_active",)}),
        ("Email", {"fields": ("default_from_email", "admin_email", "send_application_copy_to_admin")}),
        ("Social posting", {
            # your simpler set: Facebook, Reddit, Instagram only
            "fields": ("share_to_facebook", "share_to_reddit", "share_to_instagram")
        }),
    )
