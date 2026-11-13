from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import path,reverse
from django.utils.html import format_html
from board.models import EmployerMarketingProfile,MarketingSuppression,MarketingAudience,MarketingDraft
from .contacts import csv_response

@admin.register(EmployerMarketingProfile)
class ContactAdmin(admin.ModelAdmin):
    list_display=('employer','city','province','settlement','organization_type','contact_status','updated_at')
    list_filter=('settlement','province','organization_type','contact_status')
    search_fields=('employer__company_name','employer__email','employer__location','city','tags','notes')
    autocomplete_fields=('employer',)
    readonly_fields=('employer_email','updated_at')
    fields=('employer','employer_email','city','province','settlement','organization_type','tags','contact_status','outreach_basis','notes','updated_at')
    list_select_related=('employer',)
    @admin.display(description='Employer email')
    def employer_email(self,obj):return obj.employer.email if obj and obj.pk else 'Uses the existing employer email.'
    def save_model(self,request,obj,form,change):
        super().save_model(request,obj,form,change)
        if obj.contact_status in ('do_not_email','unsubscribed','bounced') and obj.employer.email:
            MarketingSuppression.objects.update_or_create(email=obj.employer.email.strip().lower(),defaults={'reason':obj.contact_status})

@admin.register(MarketingSuppression)
class SuppressionAdmin(admin.ModelAdmin):
    list_display=('email','reason','created_at');list_filter=('reason',);search_fields=('email','notes');readonly_fields=('created_at',)

@admin.register(MarketingAudience)
class AudienceAdmin(admin.ModelAdmin):
    list_display=('name','contact_count','updated_at','export_link')
    search_fields=('name','description','employers__company_name','employers__email')
    autocomplete_fields=('employers',)
    readonly_fields=('created_at','updated_at','export_link')
    def get_queryset(self,request):return super().get_queryset(request).annotate(_count=Count('employers',distinct=True))
    @admin.display(ordering='_count',description='Employers')
    def contact_count(self,obj):return obj._count
    def export_link(self,obj):
        if not obj or not obj.pk:return 'Save this audience first.'
        return format_html('<a class="button" href="{}">Export approved contacts only</a>',reverse('admin:marketing_audience_export',args=[obj.pk]))
    def get_urls(self):return [path('<int:pk>/export/',self.admin_site.admin_view(self.export),name='marketing_audience_export')]+super().get_urls()
    def export(self,request,pk):
        from django.core.exceptions import PermissionDenied
        audience=get_object_or_404(MarketingAudience,pk=pk)
        if not self.has_view_permission(request,audience) or not request.user.has_perms(['board.view_employer','board.view_employermarketingprofile']):raise PermissionDenied
        return csv_response(audience.employers.select_related('marketing_profile').order_by('company_name','pk'))

@admin.register(MarketingDraft)
class DraftAdmin(admin.ModelAdmin):
    list_display=('name','subject','audience','status','updated_at','preview_link')
    list_filter=('status','audience');search_fields=('name','subject','body');autocomplete_fields=('audience',)
    readonly_fields=('preview_link','updated_at')
    fields=('name','audience','subject','body','status','notes','preview_link','updated_at')
    def preview_link(self,obj):
        if not obj or not obj.pk:return 'Save this draft to preview it.'
        return format_html('<a class="button" href="{}" target="_blank" rel="noopener">Preview email ↗</a>',reverse('admin:marketing_draft_preview',args=[obj.pk]))
    def get_urls(self):return [path('<int:pk>/preview/',self.admin_site.admin_view(self.preview),name='marketing_draft_preview')]+super().get_urls()
    def preview(self,request,pk):
        from django.core.exceptions import PermissionDenied
        from board.notification_mail import email_frame
        obj=get_object_or_404(MarketingDraft,pk=pk)
        if not self.has_view_permission(request,obj):raise PermissionDenied
        response=HttpResponse(email_frame(obj.subject,format_html('<div style="white-space:pre-wrap">{}</div>',obj.body)))
        response['Cache-Control']='private, no-store';response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; base-uri 'none'; form-action 'none'"
        return response

from .workspace import install_contact_urls
install_contact_urls()
