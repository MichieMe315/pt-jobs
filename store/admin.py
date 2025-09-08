from django.contrib import admin
from .models import Order, OrderLine, Discount, PaymentMethod


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ("package", "qty", "unit_price_cents")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "contact_email", "total_fmt", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "contact_email", "stripe_session_id", "stripe_payment_intent")
    inlines = [OrderLineInline]
    readonly_fields = ("stripe_session_id", "stripe_payment_intent", "total_cents", "created_at", "updated_at")

    def total_fmt(self, obj):
        return f"${obj.total_cents/100:.2f}"
    total_fmt.short_description = "Total"


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "percent_off", "amount_off_cents", "active", "uses", "valid_from", "valid_to")
    list_filter = ("active",)
    search_fields = ("code", "description")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("provider", "display_name", "active", "live_mode", "created_at")
    list_filter = ("provider", "active", "live_mode")
    search_fields = ("display_name",)
