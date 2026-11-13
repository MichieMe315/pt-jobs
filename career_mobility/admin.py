from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.urls import reverse
from .models import InternationalProfile,ReferenceCost,PathwayRule,DigitalProduct,ProductOrder,ProductGalleryImage,StorefrontStudio
from .store_admin import BundleItemInline

@admin.register(InternationalProfile)
class InternationalProfileAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    readonly_fields=("email_verified_at","email_verified_address","verification_sent_at")
    list_display=("user","country_of_education","residence_country","destination_province","application_history","marketing_consent")
    list_filter=("country_of_education","residence_country","destination_province","marketing_consent")
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
    starter_quantity = forms.IntegerField(min_value=0, max_value=32767, required=False, label="Starter allowance per new account", help_text="0 = off. The count applies to downloads, exports, or bundle claims. Appointment cards count per card on the sheet.")
    from .store_eligibility import ACCOUNTS
    eligible_accounts = forms.MultipleChoiceField(
        choices=ACCOUNTS, widget=forms.CheckboxSelectMultiple, required=False,
        help_text='Leave all unchecked to use the storefront defaults. Employers cannot purchase résumés.',
    )

    class Meta:
        model = DigitalProduct
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "price_cad": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "download": forms.FileInput(attrs={"accept": ".pdf,.zip,.docx,.xlsx"}),
            "preview_image": forms.FileInput(attrs={"accept":"image/*"}),
        }

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for key, label in {'price_cad': 'Default price (CAD)', 'canadian_price_cad': 'Canadian price (CAD)', 'international_price_cad': 'International price (CAD)', 'is_published': 'Show in storefront',
                           'preview_image': 'Store cover image', 'download': 'Customer download file'}.items():
            if key in self.fields:
                self.fields[key].label = label
        if 'is_published' in self.fields:
            self.fields['is_published'].help_text = 'Leave unchecked to keep this product as a private draft.'
        if "storefront_order" in self.fields:
            self.fields["storefront_order"].required = False
        if "preview_editor" in self.fields:
            from .editable_products import TEMPLATES
            from .shop_gallery import editor_key
            key = editor_key(self.instance)
            default_label = f'Automatic · {TEMPLATES[key][0]}' if key else 'Automatic · no editor assigned'
            self.fields["preview_editor"].widget = forms.Select(choices=[
                ("", default_label), ("none", "Download only"),
                *((key, label) for key, (label, _) in TEMPLATES.items()),
            ])
        if 'kind' in self.fields:self.fields['kind'].required=False
        if 'audience' in self.fields:self.fields['audience'].required=False
        if self.instance.includes_resume_builder and "download" in self.fields:
            self.fields["download"].help_text="Optional for online resume PDF access. Add a file only if this purchase also includes a downloadable pack."

    def clean_starter_quantity(self):
        value = self.cleaned_data['starter_quantity']
        return self.instance.starter_quantity if value is None else value

    def clean_storefront_order(self):
        value = self.cleaned_data["storefront_order"]
        return self.instance.storefront_order if value is None else value

    def clean_preview_editor(self):
        from .editable_products import TEMPLATES
        key = self.cleaned_data["preview_editor"]
        if key and key != "none" and key not in TEMPLATES:
            raise ValidationError("Select a listed editor.")
        return key

    def clean_audience(self):return self.cleaned_data.get('audience') or self.instance.audience or 'both'

    def clean_kind(self):return self.cleaned_data.get('kind') or self.instance.kind or 'file'

    def clean(self):
        data=super().clean()
        if self.instance.includes_resume_builder and 'employer' in (data.get('eligible_accounts') or []):
            self.add_error('eligible_accounts', 'Employers cannot purchase résumé products.')
        if self.instance.pk and 'kind' in data and data['kind'] != self.instance.kind:
            from .models import StoreEntitlement
            if StoreEntitlement.objects.filter(product=self.instance).exists():
                self.add_error('kind','This product already grants customer access. Create another product to change its delivery type.')
        if data.get('is_published',self.instance.is_published):
            download=data.get('download',self.instance.download)
            from .editable_products import TEMPLATES
            editor = data.get('preview_editor', self.instance.preview_editor) or data.get('slug', self.instance.slug).removeprefix('ptjc-')
            if not download and data.get('kind',self.instance.kind)=='file' and not self.instance.is_online_builder and editor not in TEMPLATES:
                self.add_error('download' if 'download' in self.fields else None,'Choose an online builder or attach a finished file before publishing.')
            price=data.get('price_cad',self.instance.price_cad)
            if price is None or price<0:self.add_error('price_cad','Enter a price of $0 or more. A $0 price turns off checkout.')
        return data



class ProductGalleryForm(forms.ModelForm):
    class Meta:
        model = ProductGalleryImage
        fields = ("position", "caption", "image")
        widgets = {"image": forms.FileInput(attrs={"accept": "image/*"})}


class ProductGalleryInline(admin.StackedInline):
    form = ProductGalleryForm
    model = ProductGalleryImage
    verbose_name_plural = "Additional listing images"
    fields = ("position", "caption", "image")
    extra = 0


@admin.register(DigitalProduct)
class DigitalProductAdmin(admin.ModelAdmin):
    change_list_template="admin/career_mobility/digitalproduct/change_list.html"
    inlines=(BundleItemInline, ProductGalleryInline)
    form = DigitalProductAdminForm
    list_display = ("product_thumbnail", "title", "kind", "audience_prices", "is_published", "file_ready", "storefront_order", "shop_link")
    list_display_links = ("title",)
    list_filter = ("is_published", "kind", "audience")
    search_fields = ("title", "slug", "description")
    prepopulated_fields = {"slug": ("title",)}
    @admin.display(description="Store prices (CAD)")
    def audience_prices(self, obj):
        def label(amount):
            return f"${amount:.2f}" if amount else "Checkout off"

        if obj.audience == "canadian":
            return "Canada: " + label(obj.price_for_canadian)
        if obj.audience == "international":
            return "International: " + label(obj.price_for_international)
        return format_html("Canada: {}<br>International: {}",
                           label(obj.price_for_canadian), label(obj.price_for_international))
    change_form_template = 'admin/career_mobility/digitalproduct/change_form.html'

    @admin.display(description="Preview")
    def product_thumbnail(self, obj):
        from django.templatetags.static import static
        if obj.preview_image:
            src = reverse('admin:career_mobility_digitalproduct_store_image', args=[obj.pk])
        else:
            key = obj.slug.removeprefix('ptjc-')
            path = obj.recovered_cover or obj.journal_preview
            if not path and key in {'practice-planner-2027', 'physio-wall-calendar-2027', 'exercise-tracker', 'appointment-notes'}:
                path = f'career_mobility/product-previews/{key}.png'
            if not path and 'resume' in key:
                design = next((name for name in ('classic', 'clinical', 'editorial', 'sidebar') if key.endswith('-' + name)), 'classic')
                audience = 'canadian-' if obj.audience == 'canadian' else ''
                path = f'ptjc_resumes/designs/{audience}{design}.png'
            if not path:
                label = 'Workbook' if obj.kind == 'workbook' else 'Bundle' if obj.kind == 'bundle' else 'No cover'
                return format_html('<span class="product-list-thumb product-list-fallback">{}</span>', label)
            src = static(path)
        return format_html('<img class="product-list-thumb" src="{}" alt="" width="72" height="54" loading="lazy">', src)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj and obj.is_online_builder:
            context['product_demo_link'] = self.product_preview(obj)
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_fieldsets(self, request, obj=None):
        basics = ('title', 'short_description', 'category', 'preview_editor', 'preview_image', 'description')
        advanced = ('slug','kind','storefront_order')
        from .editable_products import JOURNALS, CALENDAR
        key = obj.slug.removeprefix('ptjc-') if obj else ''
        files = ('download','preview_image')
        if obj and key in JOURNALS:
            files += ('journal_settings',)
        return (
            ('Listing', {'fields': basics}),
            ('Price and publication', {'fields': ('is_published', 'audience', 'eligible_accounts', 'starter_quantity', 'price_cad', 'canadian_price_cad', 'international_price_cad'), 'description': 'Blank price overrides use the default. A zero price turns checkout off.'}),
            ('Customer download', {'fields': tuple(field for field in files if field != 'preview_image'), 'description': 'Leave the file unchanged to keep the current download.'}),
            ('Advanced settings', {'fields': advanced}),
        )

    def get_inlines(self, request, obj):
        return (BundleItemInline, ProductGalleryInline) if obj and obj.kind == 'bundle' else (ProductGalleryInline,)

    readonly_fields = ("shop_link", "existing_private_file", "product_preview", "journal_settings")
    ordering = ("title",)
    save_on_top = True

    def get_changelist_form(self,request,**kwargs):
        kwargs['form']=self.form
        return super().get_changelist_form(request,**kwargs)

    def get_urls(self):
        from django.urls import path
        from . import catalogue as cat
        from .product_demo import preview as product_demo
        wrap=self.admin_site.admin_view
        return [path('allowances/',wrap(lambda r:cat.starter_allowances(r,self)),name='career_mobility_digitalproduct_allowances'),path('order/',wrap(lambda r:cat.reorder(r,self)),name='career_mobility_digitalproduct_order'),path('activity/',wrap(lambda r:cat.activity_report(r,self)),name='career_mobility_digitalproduct_activity'),path('duplicates/',wrap(lambda r:cat.duplicates(r,self)),name='career_mobility_digitalproduct_duplicates'),path('<int:pk>/try/',wrap(lambda r,pk:product_demo(r,pk,self)),name='career_mobility_digitalproduct_demo'),path('<int:pk>/try/sample.pdf',wrap(lambda r,pk:product_demo(r,pk,self,pdf=True)),name='career_mobility_digitalproduct_demo_pdf'),path('<int:pk>/store-image/',wrap(lambda r,pk:cat.store_image(r,pk,self)),name='career_mobility_digitalproduct_store_image'),path('resume-import/',wrap(lambda r:cat.import_resumes(r,self)),name='career_mobility_digitalproduct_resume_import'),path('catalogue/',wrap(lambda r:cat.catalogue(r,self)),name='career_mobility_digitalproduct_catalogue'),path('import-collection/',wrap(lambda r:cat.import_collection(r,self)),name='career_mobility_digitalproduct_import'),path('<int:pk>/review/',wrap(lambda r,pk:cat.review(r,pk,self)),name='career_mobility_digitalproduct_review'),path('<int:pk>/asset/',wrap(lambda r,pk:cat.asset(r,pk,self)),name='career_mobility_digitalproduct_asset'),path('<int:pk>/view-file/',wrap(lambda r,pk:cat.preview_page(r,pk,self)),name='career_mobility_digitalproduct_view_file'),path('<int:pk>/preview/',wrap(self.preview_file),name='career_mobility_digitalproduct_preview')]+super().get_urls()

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

    @admin.display(description="Editable journal")
    def journal_settings(self, obj):
        if not obj or not obj.pk:
            return "Save the product first."
        from .models import JournalTemplate
        key = obj.preview_editor or obj.slug.removeprefix("ptjc-")
        journal = JournalTemplate.objects.filter(key=key).first()
        if not journal:
            return "Not a specialty journal."
        return format_html('<a href="{}">Edit document title, design, colour and six worksheets</a>', reverse('admin:career_mobility_journaltemplate_change',args=[journal.pk]))

    @admin.display(description="Preview this product")
    def product_preview(self,obj):
        if not obj or not obj.pk:return 'Save the product first to open its preview.'
        url=reverse('admin:career_mobility_digitalproduct_demo' if obj.is_online_builder else 'admin:career_mobility_digitalproduct_review',args=[obj.pk])
        label='Open interactive business-card preview ↗' if obj.includes_card_builder else 'Open interactive resume builder ↗' if obj.includes_resume_builder else 'Open product files and previews ↗'
        return format_html('<a class="button" href="{}" target="_blank" rel="noopener">{}</a>',url,label)

    @admin.display(description="Current private download")
    def existing_private_file(self, obj):
        if obj.pk and obj.includes_resume_builder and not obj.download:
            return "PDFs are generated from the customer’s saved resume. No uploaded file is required."
        if not obj.pk or not obj.download:
            return "No file uploaded"
        # FileField.name is metadata; never call .url on private storage.
        from pathlib import PurePosixPath
        return format_html('<a href="{}">Review files and previews: {}</a>', reverse("admin:career_mobility_digitalproduct_review", args=[obj.pk]), PurePosixPath(obj.download.name).name)

    @admin.display(description="Customer delivery")
    def file_ready(self, obj):
        if obj.kind == 'bundle':
            return 'Bundle'
        if obj.kind == 'workbook':
            return 'Personalized workbook'
        if obj.is_online_builder or obj.has_editable_preview:
            return 'Online builder'
        return 'Download only' if obj.download else 'Missing file or builder'

    @admin.display(description="Storefront")
    def shop_link(self, obj):
        if not obj.pk or not obj.is_published:
            return "Private draft"
        from .shop_gallery import resource_link
        url = resource_link(obj, 'international' if obj.audience == 'international' else 'canadian')
        if not url:
            return "Published · no editor listing"
        return format_html('<a href="{}" target="_blank" rel="noopener">Open customer tool ↗</a>', url)


@admin.register(ProductOrder)
class ProductOrderAdmin(admin.ModelAdmin):
    list_display=("user","product","paid","paid_amount","created_at")
    readonly_fields=("user","product","stripe_session_id","paid","checkout_state","amount_cents","list_amount_cents","discount_amount_cents","discount","currency","checkout_snapshot","created_at")
    list_filter=('paid','created_at')
    search_fields=('user__email','user__username','product__title','stripe_session_id')
    list_select_related=('user','product')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    @admin.display(description='Checkout amount')
    def paid_amount(self,obj):
        return f'{obj.currency} {obj.amount_cents/100:,.2f}' if obj.amount_cents is not None else 'Not recorded (legacy order)'

from .models import DataSource, DataSourceReview

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    actions=['fetch_wage_review']
    @admin.action(description='Fetch official wage or rent feed for review')
    def fetch_wage_review(self,request,queryset):
        from .research_refresh import fetch
        from django.contrib import messages
        if not self.has_change_permission(request):raise PermissionError
        for source in queryset:
            try:
                review=fetch(source);self.message_user(request,'Source figures queued for review: '+str(review),messages.SUCCESS)
            except (ValueError,OSError) as exc:self.message_user(request,str(exc),messages.ERROR)
    list_display = ("name", "category", "cadence", "enabled", "last_checked_at", "last_changed_at", "last_http_status")
    list_filter = ("category", "cadence", "enabled")
    search_fields = ("name", "url")
    readonly_fields = ("last_checked_at", "last_changed_at", "last_http_status", "content_sha256", "last_error")

@admin.register(DataSourceReview)
class DataSourceReviewAdmin(admin.ModelAdmin):
    exclude=('detail',)
    def source_values(self,obj):
        import json
        from django.utils.html import format_html,format_html_join
        try:data=json.loads(obj.detail)
        except (ValueError,TypeError):return obj.detail
        if not isinstance(data,dict) or not isinstance(data.get('rows'),list):return 'This source change needs manual review; no numeric import is available.'
        rows=data['rows'];wages=data.get('kind')=='jobbank_pt_wages';values=[]
        for row in rows[:1000]:
            if not isinstance(row,dict):continue
            common=(row.get('region') or row.get('city',''),row.get('province',''),row.get('reference_period',''))
            if wages:values.append(common+(row.get('low_hourly') or 'Not published',row.get('median_hourly') or 'Not published',row.get('high_hourly') or 'Not published'))
            else:values.append(common+(row.get('amount_cad') or 'Not published',))
        headers=['Area','Province','Period']+(['Low CAD/hour','Median CAD/hour','High CAD/hour'] if wages else ['Two-bedroom rent CAD/month'])
        head=format_html_join('','<th>{}</th>',[(h,) for h in headers])
        body=format_html_join('','<tr>'+''.join('<td>{}</td>' for h in headers)+'</tr>',values)
        return format_html('<div class="pt-dashboard-table-wrap"><p>{} · {} source rows. Check the period, geography and amounts before approving.</p><table class="pt-dashboard-table"><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>','Physiotherapist wages' if wages else 'Municipal rents',len(rows),head,body)
    source_values.short_description='Figures awaiting review'
    actions=['publish_wage_review']
    @admin.action(description='Approve and publish reviewed source figures')
    def publish_wage_review(self,request,queryset):
        from .research_refresh import approve
        from django.contrib import messages
        if not self.has_change_permission(request):raise PermissionError
        for review in queryset:
            try:self.message_user(request,str(approve(review))+' reviewed source records published.',messages.SUCCESS)
            except (ValueError,KeyError) as exc:self.message_user(request,str(exc),messages.ERROR)
    list_display = ("source", "detected_at", "status", "reviewed_at")
    list_filter = ("status", "source__category")
    search_fields = ("source__name", "detail")
    readonly_fields = ("source", "detected_at", "previous_hash", "detected_hash", "source_values", "reviewed_at")

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        if change and "status" in form.changed_data and obj.status == "approved" and any(k in obj.detail for k in ('"kind": "jobbank_pt_wages"','"kind": "alberta_municipal_rents"')):
            from .research_refresh import approve
            approve(obj)
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

from .models import CalculatorUsageEvent

@admin.register(CalculatorUsageEvent)
class CalculatorUsageAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        from datetime import timedelta
        from django.core.exceptions import PermissionDenied
        from django.db.models import Count, Q
        from django.db.models.functions import TruncDate
        from django.template.response import TemplateResponse
        from django.utils import timezone
        if not self.has_view_permission(request):
            raise PermissionDenied
        all_time = request.GET.get('days') == 'all'
        try:
            days = int(request.GET.get('days', '30'))
        except (TypeError, ValueError):
            days = 30
        if days not in (1, 7, 30, 90, 365):
            days = 30
        today = timezone.localdate()
        start = today - timedelta(days=days-1)
        from django.core.paginator import Paginator
        first = CalculatorUsageEvent.objects.order_by('created_at').values_list('created_at', flat=True).first()
        if all_time and first:
            start = timezone.localtime(first).date()
        qs = CalculatorUsageEvent.objects.filter(created_at__date__gte=start, created_at__date__lte=today)
        names = CalculatorUsageEvent.EVENTS
        counts = {name: Count('pk', filter=Q(event=name)) for name, label in names}
        totals = qs.aggregate(**counts, sessions=Count('session_hash', distinct=True))
        started = qs.filter(event='salary_calculator_start').values('session_hash')
        started_sessions = started.distinct().count()
        completed_started = qs.filter(event='salary_comparison_complete', session_hash__in=started).values('session_hash').distinct().count()
        daily = qs.annotate(day=TruncDate('created_at')).values('day').annotate(**counts, sessions=Count('session_hash', distinct=True)).order_by('-day')
        if all_time:
            page = Paginator(daily, 31).get_page(request.GET.get('page'))
            rows = [{'day': row['day'], 'values': [row[name] for name, _ in names], 'sessions': row['sessions']} for row in page]
        else:
            page = None
            by_day = {row['day']: row for row in daily}
            rows = []
            for offset in range(days):
                day = today - timedelta(days=offset)
                values = by_day.get(day, {})
                rows.append({'day': day, 'values': [values.get(name, 0) for name, label in names], 'sessions': values.get('sessions', 0)})
        context = {**self.admin_site.each_context(request), 'title': 'Calculator usage',
            'opts': self.model._meta, 'days': days, 'all_time': all_time, 'page': page, 'start': start, 'today': today,
            'cards': [{'label': label, 'value': totals[name]} for name, label in names],
            'sessions': totals['sessions'], 'started_sessions': started_sessions, 'completion_rate': round(100 * completed_started / started_sessions) if started_sessions else None, 'rows': rows, 'first_event': first,
            'countries': qs.values('country').annotate(sessions=Count('session_hash', distinct=True), events=Count('pk')).order_by('-sessions'),
        }
        return TemplateResponse(request, 'admin/career_mobility/calculator_usage.html', context)

from .models import InternationalActivity, CountryResourceCollection

@admin.register(InternationalActivity)
class InternationalActivityAdmin(admin.ModelAdmin):
    list_display=('created_at','person','action','visitor_country','education_country','residence_country','page_country','subject')
    list_filter=('action','visitor_country','education_country','residence_country','page_country','created_at')
    search_fields=('profile__user__email','profile__user__username','subject')
    date_hierarchy='created_at'
    list_select_related=('profile__user',)
    list_per_page=50
    change_list_template='admin/career_mobility/international_activity.html'
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    @admin.display(description='Account')
    def person(self,obj):
        if not obj.profile_id:return 'Anonymous / deleted account'
        return obj.profile.user.email or obj.profile.user.username
    def changelist_view(self,request,extra_context=None):
        from django.db.models import Count,Q
        from django.core.exceptions import PermissionDenied
        if not self.has_view_permission(request):raise PermissionDenied
        qs=self.get_changelist_instance(request).get_queryset(request)
        totals=qs.aggregate(actions=Count('pk'),accounts=Count('profile_id',distinct=True),signups=Count('pk',filter=Q(action='account_created')),purchases=Count('pk',filter=Q(action='purchase_confirmed')),downloads=Count('pk',filter=Q(action__in=['country_guide_downloaded','product_downloaded','checklist_downloaded'])))
        return super().changelist_view(request,extra_context={'activity_totals':totals,**(extra_context or {})})

from .countries import COUNTRIES as EDUCATION_COUNTRIES
from .country_content import get_country as education_country

class CountryResourceCollectionForm(forms.ModelForm):
    country_slug=forms.ChoiceField(label='Education country',choices=[('', 'Choose a country')]+[(education_country(name)['slug'],name) for name in EDUCATION_COUNTRIES])
    class Meta:
        model=CountryResourceCollection
        fields='__all__'

@admin.register(CountryResourceCollection)
class CountryResourceCollectionAdmin(admin.ModelAdmin):
    form=CountryResourceCollectionForm
    list_display=('title','country_slug','is_published','bundle_product')
    list_filter=('is_published',)
    filter_horizontal=('products',)
    fields=('country_slug','title','description','products','bundle_product','is_published')
    actions=('build_private_bundle',)
    @admin.action(description='Build private ZIP bundle from selected collection files')
    def build_private_bundle(self,request,queryset):
        from .bundles import build_bundle
        from django.core.exceptions import PermissionDenied
        from django.contrib import messages
        if not request.user.has_perm('career_mobility.change_countryresourcecollection') or not request.user.has_perm('career_mobility.add_digitalproduct') or not request.user.has_perm('career_mobility.change_digitalproduct'):
            raise PermissionDenied
        for collection in queryset:
            try:
                product=build_bundle(collection)
                self.message_user(request,f'{collection.title}: private ZIP saved. Review the files, set its price and publish the bundle product separately.',messages.SUCCESS)
            except (ValueError,OSError) as exc:
                self.message_user(request,f'{collection.title}: {exc}',messages.ERROR)

# Only explicitly enabled international operations are added to production admin.
from django.conf import settings
from .international_activity import enabled
keep={SavedCareerPlan,CalculatorUsageEvent}
if enabled():
    from .models import StoreDiscount, StoreGrant, StoreEntitlement
    keep.update({InternationalProfile,DigitalProduct,ProductOrder,InternationalActivity,CountryResourceCollection,InternationalChecklistItem,StoreDiscount,StoreGrant,StoreEntitlement})
if not settings.CAREER_TOOLS_PREVIEW:
    for model in tuple(admin.site._registry):
        if model._meta.app_label == 'career_mobility' and model not in keep:
            admin.site.unregister(model)


@admin.register(StorefrontStudio)
class StorefrontStudioAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (
        ('Editor listing', {
            'fields': ('key', 'title', 'description', 'position', 'is_visible'),
            'description': 'These listing details apply when the editor has no published product. Edit the product in the catalogue to change a published title, description, cover or order.',
        }),
    )
    readonly_fields = ("key",)
    list_display = ("title", "position", "is_visible")
    list_editable = ("position", "is_visible")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from . import journal_admin


from .models import InternationalSponsor
from .countries import COUNTRIES


class InternationalSponsorForm(forms.ModelForm):
    country = forms.ChoiceField(choices=[('', 'All countries'), *((c, c) for c in COUNTRIES)], required=False)

    class Meta:
        model = InternationalSponsor
        fields = '__all__'


@admin.register(InternationalSponsor)
class InternationalSponsorAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    form = InternationalSponsorForm
    list_display = ('sponsor', 'country', 'enabled', 'position')
    list_filter = ('enabled', 'country')
    list_editable = ('enabled', 'position')
    search_fields = ('sponsor', 'country')
