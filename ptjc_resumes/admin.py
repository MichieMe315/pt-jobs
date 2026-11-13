from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from .models import ResumeTemplate, ResumeDraft, ResumeLayoutOffer

class ResumeLayoutOfferInline(admin.TabularInline):
    model = ResumeLayoutOffer
    extra = 0
    fields = ('layout', 'product', 'publication')
    readonly_fields = ('publication',)
    def get_autocomplete_fields(self, request):
        product_model = self.model._meta.get_field('product').remote_field.model
        return ('product',) if self.admin_site.is_registered(product_model) else ()

    @admin.display(description='Individual shop listing')
    def publication(self, offer):
        if not offer.product_id:
            return 'No product selected'
        return 'Published' if offer.product.is_published else 'Private draft'


@admin.register(ResumeTemplate)
class ResumeTemplateAdmin(admin.ModelAdmin):
    change_list_template = 'admin/ptjc_resumes/resumetemplate/change_list.html'
    change_form_template = 'admin/workspace/record_editor.html'
    list_display = ('title', 'access_product', 'price', 'checkout_status', 'sample_link', 'is_enabled')
    list_select_related = ('access_product',)
    inlines = (ResumeLayoutOfferInline,)
    list_filter = ('is_enabled',)
    list_display = (*list_display, 'design_availability')
    fields = ('title', 'key', 'default_layout', 'default_palette', 'access_product', 'price', 'checkout_status', 'sample_link', 'is_enabled', 'design_availability')
    readonly_fields = ('price','checkout_status','sample_link','design_availability')
    @admin.display(description='Available designs')
    def design_availability(self, obj):
        if not obj or not obj.pk:
            return 'Save this builder first.'
        if not obj.is_enabled:
            return 'Builder disabled'
        from django.utils.html import format_html_join
        offers = {row.layout: row.product for row in obj.layout_offers.select_related('product')}
        audience = 'canadian' if obj.key == 'canadian-professional' else 'international'
        def published(product):
            return product and product.is_published and product.audience in (audience, 'both')
        bundle = obj.access_product if obj.access_product_id else None
        return format_html_join(
            ', ', '{}: {}',
            ((name.title(), 'Individual download' if published(offers.get(name))
              else 'All-design access' if published(bundle) else 'Preview only')
             for name in ('classic', 'clinical', 'editorial', 'sidebar')),
        )

    def checkout_status(self,obj):
        if not obj or not obj.access_product_id:return 'Connect a shop product, set its price, then publish it.'
        product=obj.access_product
        if not obj.is_enabled:return 'Resume builder is disabled.'
        amount = self._price_for_template(obj)
        if amount < 0:return 'Set a valid price in the linked shop product.'
        if not product.is_published:return 'Price is set. Publish the linked shop product to enable purchasing.'
        if not amount:
            return 'Checkout off. Starter allowances are managed in Digital products.'
        from career_mobility.store_config import stripe_key,webhook_secret
        if not stripe_key() or not webhook_secret():return 'Configure the digital webhook signing secret. The existing PT Jobs Stripe API key can be reused.'
        return 'Ready: published product, price set, payment configuration present.'
    def get_urls(self):
        return [path('<int:pk>/sample.pdf',self.admin_site.admin_view(self.sample),name='ptjc_resumes_resumetemplate_sample')]+super().get_urls()
    def sample(self,request,pk):
        from django.core.exceptions import PermissionDenied
        from django.shortcuts import get_object_or_404
        from django.http import HttpResponse
        obj=get_object_or_404(ResumeTemplate,pk=pk)
        if not self.has_view_permission(request,obj):raise PermissionDenied
        from .schema import normalize, CANADIAN_EXAMPLE
        from .designs import IEPT_PREVIEW
        from .pdf import render_pdf
        response=HttpResponse(render_pdf(normalize({**(CANADIAN_EXAMPLE if obj.key == "canadian-professional" else IEPT_PREVIEW), **obj.design_defaults()}), example=True, canadian=obj.key == "canadian-professional"),content_type='application/pdf')
        response['Content-Disposition']='inline; filename="resume-example.pdf"'
        response['Cache-Control']='private, no-store'
        return response
    def sample_link(self,obj):
        if not obj or not obj.pk:return 'Save the template first.'
        return format_html('<a href="{}" target="_blank" rel="noopener">Preview the saved default design ↗</a>',reverse('admin:ptjc_resumes_resumetemplate_sample',args=[obj.pk]))
    def _price_for_template(self, obj):
        audience = 'canadian' if obj.key == 'canadian-professional' else 'international'
        return obj.access_product.price_for(audience)

    def price(self, obj):
        if not obj or not obj.access_product_id:
            return 'Select the shop product first.'
        return format_html('<a href="{}">CAD ${} — edit shop price</a>', reverse('admin:career_mobility_digitalproduct_change', args=[obj.access_product_id]) + '#pricing', self._price_for_template(obj))

@admin.register(ResumeDraft)
class ResumeDraftAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display = ('title', 'owner', 'template', 'updated_at')
    list_select_related = ('owner', 'template')
    readonly_fields = ('id', 'owner', 'template', 'title', 'data', 'revision', 'created_at', 'updated_at')
    search_fields = ('title', 'owner__email')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

from .models import ResumeAdPlacement
@admin.register(ResumeAdPlacement)
class ResumeAdAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display=('title','enabled','mode','show_on_international_planner')
    fields=('title','enabled','mode','html','adsense_client','adsense_slot','show_on_international_planner')
    def has_add_permission(self,request):return not ResumeAdPlacement.objects.exists() and super().has_add_permission(request)

from .models import BusinessCardDraft
@admin.register(BusinessCardDraft)
class BusinessCardDraftAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display=('title','owner','updated_at')
    search_fields=('owner__email','title')
    readonly_fields=('id','owner','title','data','revision','updated_at')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
