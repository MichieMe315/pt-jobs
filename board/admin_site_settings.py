# board/admin_site_settings.py
from django.contrib import admin
from .models_site import SiteEmailSettings

@admin.register(SiteEmailSettings)
class SiteEmailSettingsAdmin(admin.ModelAdmin):
    list_display = ("default_from_email", "admin_email", "send_application_copy_to_admin", "is_active")
    list_filter = ("is_active", "send_application_copy_to_admin")
    search_fields = ("default_from_email", "admin_email")
