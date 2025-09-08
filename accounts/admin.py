from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "company_name", "website")
    search_fields = ("user__username", "company_name", "website")
    list_filter = ("role",)




