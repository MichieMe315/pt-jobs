from django.contrib import admin
from .models import Company, Job, Application

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'website')

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'city', 'province', 'employment_type', 'is_active', 'created_at')
    list_filter = ('employment_type', 'province', 'is_active', 'created_at')

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('job', 'applicant', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at')
