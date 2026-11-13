from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .admin_section_models import (
    AffiliateCommission, AffiliatePartner, AffiliateProgram, AffiliateReferral,
    EmailDeliveryLog, SignupAnswer, SignupQuestion, WebsitePage,
)


class Editor(admin.ModelAdmin):
    change_form_template = "admin/workspace/record_editor.html"


@admin.register(WebsitePage)
class WebsitePageAdmin(Editor):
    list_display = ("title", "slug", "published", "header", "footer", "position")
    list_editable = ("published", "header", "footer", "position")
    search_fields = ("title", "slug", "body")
    list_filter = ("published", "header", "footer")
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (("Page", {"fields": ("title", "slug", "body")}),
                 ("Publishing and SEO", {"fields": ("seo_description", "published", "header", "footer", "position")}))


@admin.register(SignupQuestion)
class SignupQuestionAdmin(Editor):
    list_display = ("label", "audience", "kind", "required", "enabled", "position")
    list_filter = ("audience", "enabled", "kind")
    list_editable = ("enabled", "position")
    search_fields = ("label",)
    fieldsets = (("Question", {"fields": ("audience", "label", "help_text", "kind", "options")}),
                 ("Signup placement", {"fields": ("enabled", "required", "position")}))


class ReadOnly(Editor):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SignupAnswer)
class SignupAnswerAdmin(ReadOnly):
    list_display = ("user", "label_at_signup", "answer", "created_at")
    list_filter = ("question__audience",)
    search_fields = ("user__email", "label_at_signup", "answer")
    ordering = ("-created_at",)


@admin.register(AffiliateProgram)
class AffiliateProgramAdmin(Editor):
    list_display = ("__str__", "enabled", "applications_open", "default_rate")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AffiliatePartner)
class AffiliatePartnerAdmin(Editor):
    list_display = ("code", "user", "status", "rate", "created_at")
    list_filter = ("status",)
    search_fields = ("code", "user__email", "website")
    readonly_fields = ("user", "code", "terms_accepted_at", "created_at")
    actions = ("approve",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Approve selected pending applications", permissions=["change"])
    def approve(self, request, queryset):
        count = queryset.filter(status="pending", terms_accepted_at__isnull=False, user__is_active=True).update(status="approved")
        self.message_user(request, f"{count} application(s) approved.", messages.SUCCESS)


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(ReadOnly):
    list_display = ("partner", "user", "created_at")
    search_fields = ("partner__code", "user__email")
    ordering = ("-created_at",)


class CommissionForm(forms.ModelForm):
    class Meta:
        model = AffiliateCommission
        fields = ("invoice",)

    def clean_invoice(self):
        invoice = self.cleaned_data["invoice"]
        if transaction.get_connection().in_atomic_block:
            invoice = type(invoice).objects.select_for_update().get(pk=invoice.pk)
        program = AffiliateProgram.objects.filter(pk=1, enabled=True).first()
        referral = AffiliateReferral.objects.select_related("partner").filter(
            user=invoice.employer.user, partner__status="approved", partner__user__is_active=True,
            created_at__lte=invoice.order_date).first()
        if not program or not referral or referral.partner.user_id == referral.user_id or invoice.status != "paid" or invoice.currency != "CAD":
            raise ValidationError("Choose a paid CAD employer invoice placed after a valid referral while the program is enabled.")
        rate = referral.partner.rate if referral.partner.rate is not None else program.default_rate
        cents = int((Decimal(invoice.amount) * rate / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if cents <= 0 or AffiliateCommission.objects.filter(invoice=invoice).exists():
            raise ValidationError("This invoice has no payable commission or is already recorded.")
        self.instance.referral = referral
        self.instance.rate = rate
        self.instance.cents = cents
        return invoice


class RecordPayoutForm(forms.ModelForm):
    confirm_payment = forms.BooleanField(required=False, label="Confirm the partner was paid outside PTJC")

    def clean(self):
        data = super().clean()
        reference = data.get("payment_reference", "")
        if not self.instance.paid_at and (reference or data.get("confirm_payment")):
            if not reference or not data.get("confirm_payment"):
                raise ValidationError("Enter the payment reference and confirm that payment was sent.")
            if not type(self.instance.invoice).objects.filter(pk=self.instance.invoice_id, status="paid", currency="CAD").exists():
                raise ValidationError("This invoice is no longer paid in CAD. Review it before recording a payout.")
        return data


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(Editor):
    form = CommissionForm
    list_display = ("invoice", "referral", "rate", "amount", "paid_at", "payment_reference")
    search_fields = ("invoice__processor_reference", "referral__partner__code", "payment_reference")
    raw_id_fields = ("invoice",)
    readonly_fields = ("referral", "rate", "cents", "paid_at")
    ordering = ("-created_at",)

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("invoice",)
        fields = ("invoice", "referral", "rate", "cents", "payment_reference", "paid_at")
        return fields if obj.paid_at else (*fields, "confirm_payment")

    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return self.readonly_fields
        return (*self.readonly_fields, "invoice", *(("payment_reference",) if obj.paid_at else ()))

    def get_form(self, request, obj=None, **kwargs):
        # An existing commission permits only entry of the external payment reference.
        if obj:
            kwargs["form"] = RecordPayoutForm
        return super().get_form(request, obj, **kwargs)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id and request.method == "POST":
            with transaction.atomic():
                self.get_queryset(request).select_for_update().filter(pk=object_id).first()
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change and obj.payment_reference and not obj.paid_at:
            obj.paid_at = timezone.now()
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return request.user.has_perm("board.view_invoice") and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Commission (CAD)")
    def amount(self, obj):
        return f"${Decimal(obj.cents) / 100:.2f}"


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(ReadOnly):
    list_display = ("created_at", "recipients", "subject", "outcome", "detail")
    list_filter = ("outcome", ("created_at", admin.DateFieldListFilter))
    search_fields = ("recipients", "subject", "detail")
    ordering = ("-created_at",)
    list_per_page = 50
