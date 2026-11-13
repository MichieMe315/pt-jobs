from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from board.models import EmployerMarketingProfile,MarketingAudience

def classify(queryset,request,field,value):
    if not request.user.has_perms(['board.add_employermarketingprofile','board.change_employermarketingprofile']):raise PermissionDenied
    with transaction.atomic():
        for employer in queryset:EmployerMarketingProfile.objects.update_or_create(employer=employer,defaults={field:value})

@admin.action(description='Marketing: classify selected as rural',permissions=['change'])
def mark_rural(modeladmin,request,queryset):classify(queryset,request,'settlement','rural')
@admin.action(description='Marketing: classify selected as remote',permissions=['change'])
def mark_remote(modeladmin,request,queryset):classify(queryset,request,'settlement','remote')
@admin.action(description='Marketing: classify selected as small city / regional centre',permissions=['change'])
def mark_small_city(modeladmin,request,queryset):classify(queryset,request,'settlement','small_city')
@admin.action(description='Marketing: classify selected as clinics',permissions=['change'])
def mark_clinics(modeladmin,request,queryset):classify(queryset,request,'organization_type','clinic')
@admin.action(description='Marketing: classify selected as hospitals',permissions=['change'])
def mark_hospitals(modeladmin,request,queryset):classify(queryset,request,'organization_type','hospital')
@admin.action(description='Marketing: save selected employers as an audience',permissions=['view'])
def save_audience(modeladmin,request,queryset):
    if not request.user.has_perm('board.add_marketingaudience'):raise PermissionDenied
    with transaction.atomic():
        audience=MarketingAudience.objects.create(name='Employer selection — '+timezone.localtime().strftime('%Y-%m-%d %H:%M'))
        audience.employers.set(queryset.values_list('pk',flat=True))
    return redirect('admin:board_marketingaudience_change',audience.pk)
