from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.urls import reverse
from .models import InternationalProfile,ReferenceCost,PathwayRule,DigitalProduct,ProductOrder

@admin.register(InternationalProfile)
class InternationalProfileAdmin(admin.ModelAdmin):
    list_display=("user","country_of_education","destination_province","capr_stage","marketing_consent")
    list_filter=("country_of_education","destination_province","marketing_consent")
    search_fields=("user__email","user__username")

@admin.register(ReferenceCost)
class ReferenceCostAdmin(admin.ModelAdmin):
    list_display=("kind","city","province","amount_cad","verified_on","is_published")
    list_filter=("kind","province","is_published")
    search_fields=("city","province")

@admin.register(PathwayRule)
class PathwayRuleAdmin(admin.ModelAdmin):
    list_display=("country","pathway_label","verified_on","is_published")
    list_filter=("is_published",)
    search_fields=("country",)

class DigitalProductAdminForm(forms.ModelForm):
    class Meta:
        model = DigitalProduct
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "price_cad": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "download": forms.FileInput(attrs={"accept": ".pdf,.zip,.docx,.xlsx"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("is_published"):
            if not data.get("download"):
                self.add_error("download", "Upload a finished digital product before publishing it.")
            if data.get("price_cad") is None or data["price_cad"] <= 0:
                self.add_error("price_cad", "Enter a price above $0 before publishing. Free products require a separate fulfillment workflow.")
        return data


@admin.register(DigitalProduct)
class DigitalProductAdmin(admin.ModelAdmin):
    form = DigitalProductAdminForm
    list_display = ("title", "price_cad", "is_published", "file_ready", "shop_link")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("price_cad",)  # Admin-editable pricing without a migration.
    fields = ("title", "slug", "description", "price_cad", "download", "existing_private_file", "is_published", "shop_link")
    readonly_fields = ("shop_link", "existing_private_file",)
    ordering = ("title",)
    save_on_top = True

    def get_urls(self):
        from django.urls import path
        return [path("<int:pk>/preview/", self.admin_site.admin_view(self.preview_file), name="career_mobility_digitalproduct_preview")] + super().get_urls()

    def preview_file(self, request, pk):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404
        from django.http import FileResponse, Http404
        obj = get_object_or_404(DigitalProduct, pk=pk)
        if not self.has_view_permission(request, obj):
            raise PermissionDenied
        if not obj.download:
            raise Http404
        response = FileResponse(obj.download.open("rb"), as_attachment=True, filename=obj.download.name.rsplit("/", 1)[-1])
        response["Cache-Control"] = "private, no-store"
        return response

    @admin.display(description="Current private download")
    def existing_private_file(self, obj):
        if not obj.pk or not obj.download:
            return "No file uploaded"
        # FileField.name is metadata; never call .url on private storage.
        from pathlib import PurePosixPath
        return format_html('<a href="{}">Review uploaded file: {}</a>', reverse("admin:career_mobility_digitalproduct_preview", args=[obj.pk]), PurePosixPath(obj.download.name).name)

    @admin.display(boolean=True, description="File uploaded")
    def file_ready(self, obj):
        return bool(obj.download)

    @admin.display(description="Storefront")
    def shop_link(self, obj):
        if not obj.pk or not obj.is_published:
            return "Publish to display in the shop"
        return format_html('<a href="{}" target="_blank" rel="noopener">View shop</a>', reverse("ptjc_shop"))

@admin.register(ProductOrder)
class ProductOrderAdmin(admin.ModelAdmin):
    list_display=("user","product","paid","created_at")
    readonly_fields=("user","product","stripe_session_id","paid","created_at")

from .models import DataSource, DataSourceReview

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "cadence", "enabled", "last_checked_at", "last_changed_at", "last_http_status")
    list_filter = ("category", "cadence", "enabled")
    search_fields = ("name", "url")
    readonly_fields = ("last_checked_at", "last_changed_at", "last_http_status", "content_sha256", "last_error")

@admin.register(DataSourceReview)
class DataSourceReviewAdmin(admin.ModelAdmin):
    list_display = ("source", "detected_at", "status", "reviewed_at")
    list_filter = ("status", "source__category")
    search_fields = ("source__name", "detail")
    readonly_fields = ("source", "detected_at", "previous_hash", "detected_hash", "detail", "reviewed_at")

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        if change and "status" in form.changed_data and obj.status != "pending":
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


from .models import ProvincialLicenceFee

@admin.register(ProvincialLicenceFee)
class ProvincialLicenceFeeAdmin(admin.ModelAdmin):
    list_display = ("province", "description", "fee_type", "amount_cad", "effective_on", "verified_on", "is_published")
    list_filter = ("province", "fee_type", "is_published")
    search_fields = ("province", "regulator", "description", "applies_to")
    list_editable = ()  # Do not bypass model validation with bulk list editing.
    actions = None  # Publication must go through validated single-record edit.

from .models import InternationalChecklistItem, SavedCareerPlan, SalaryBenchmark
@admin.register(SalaryBenchmark)
class SalaryBenchmarkAdmin(admin.ModelAdmin):
    list_display=("region","median_hourly","reference_period","verified_on","is_published")
    list_filter=("province","is_published")
    search_fields=("region",)
@admin.register(InternationalChecklistItem)
class InternationalChecklistAdmin(admin.ModelAdmin):
    list_display=("profile","key","completed","updated_at")
    list_filter=("completed","key")
# Operational visibility for saved comparisons; private candidate data is never
# exposed on the public storefront or to other candidates.
from .models import SavedCareerPlan

@admin.register(SavedCareerPlan)
class SavedCareerPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "plan_type", "created_at")
    list_filter = ("plan_type", "created_at")
    search_fields = ("title", "user__email", "user__username")
    readonly_fields = ("user", "plan_type", "title", "inputs", "created_at")
    ordering = ("-created_at",)
    list_per_page = 40
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False

# The initial production release exposes salary records only in admin.
from django.conf import settings
if not settings.CAREER_TOOLS_PREVIEW:
    for model in tuple(admin.site._registry):
        if model._meta.app_label == 'career_mobility' and model is not SavedCareerPlan:
            admin.site.unregister(model)
