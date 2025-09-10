from django.contrib import admin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from .models import UserProfile
from .resources import UserProfileResource

@admin.register(UserProfile)
class UserProfileAdmin(ImportExportModelAdmin):
    resource_classes = [UserProfileResource]

    list_display = ("user", "user_email", "role", "company_name", "website", "approved")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "company_name", "website")

    fieldsets = (
        ("Account", {"fields": ("user", "role")}),
        ("Organization", {"fields": ("company_name", "website")}),
        ("Profile", {"fields": ("bio",)}),  # <-- fixed: tuple, not string
    )

    actions = ("approve_selected", "unapprove_selected")

    @admin.display(boolean=True, description="Approved?")
    def approved(self, obj):
        return bool(obj.user and obj.user.is_active)

    @admin.display(description="Email")
    def user_email(self, obj):
        return obj.user.email if obj.user else ""

    @admin.action(description="Approve selected users (set user.is_active=True)")
    def approve_selected(self, request, queryset):
        User.objects.filter(id__in=queryset.values_list("user_id", flat=True)).update(is_active=True)

    @admin.action(description="Unapprove selected users (set user.is_active=False)")
    def unapprove_selected(self, request, queryset):
        User.objects.filter(id__in=queryset.values_list("user_id", flat=True)).update(is_active=False)

# (Optional) Show Profile inline on the User page
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"

class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
