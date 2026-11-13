from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import StoreBundleItem,StoreDiscount,StoreGrant,StoreEntitlement
from .store_access import activate_grant

class BundleItemInline(admin.TabularInline):
    model=StoreBundleItem
    fk_name='bundle'
    autocomplete_fields=('product',)
    extra=0
    def get_queryset(self,request):return super().get_queryset(request).select_related('product')

@admin.register(StoreDiscount)
class DiscountAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display=('name','code','kind','value','is_active','starts_at','ends_at')
    list_filter=('kind','is_active')
    search_fields=('name','code')
    filter_horizontal=('products',)
    fields=('name','code','products','kind','value','starts_at','ends_at','max_uses','max_uses_per_user','is_active')

@admin.register(StoreGrant)
class GrantAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display=('user','product','quantity','active','activated_at')
    list_filter=('active','product__kind')
    search_fields=('user__email','product__title','reason')
    autocomplete_fields=('user','product')
    readonly_fields=('created_at','activated_at')
    def get_readonly_fields(self,request,obj=None):
        return self.readonly_fields+(('user','product','quantity') if obj and obj.activated_at else ())
    def save_model(self,request,obj,form,change):
        super().save_model(request,obj,form,change)
        activate_grant(obj)

@admin.register(StoreEntitlement)
class EntitlementAdmin(admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_display=('user','product','remaining','order','grant','created_at')
    list_filter=('product__kind',)
    search_fields=('user__email','product__title')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
