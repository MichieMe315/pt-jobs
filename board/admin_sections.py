from django import forms
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .admin_section_models import AffiliatePartner, AffiliateProgram, AffiliateReferral, SignupAnswer, SignupQuestion, WebsitePage


def website_page(request, slug):
    page = get_object_or_404(WebsitePage, slug=slug, published=True)
    return render(request, "board/website_page.html", {"page": page})


def signup_questions(form, audience):
    fields = []
    for question in SignupQuestion.objects.filter(audience=audience, enabled=True):
        key = f"extra_{question.pk}"
        common = dict(label=question.label, required=question.required, help_text=question.help_text)
        if question.kind == "choice":
            field = forms.ChoiceField(choices=[("", "Select an option"), *((value, value) for value in question.choices())], **common)
        else:
            field = forms.CharField(max_length=2000 if question.kind == "long" else 250,
                widget=forms.Textarea(attrs={"rows": 3}) if question.kind == "long" else forms.TextInput(), **common)
        field.widget.attrs["class"] = "form-select" if question.kind == "choice" else "form-control"
        form.fields[key] = field
        fields.append((question, key))
    form.extra_fields = [form[key] for _, key in fields]
    return fields


def save_signup(request, form, fields, *, allow_referral=False):
    with transaction.atomic():
        user = form.save()
        SignupAnswer.objects.bulk_create([
            SignupAnswer(user=user, question=question, label_at_signup=question.label, answer=value)
            for question, key in fields if (value := form.cleaned_data.get(key))
        ])
        if allow_referral:
            code = request.session.get("ptjc_affiliate_code")
            recorded = request.session.get("ptjc_affiliate_at", 0)
            age = int(timezone.now().timestamp()) - recorded
            if code and 0 <= age <= 30 * 86400 and AffiliateProgram.objects.filter(pk=1, enabled=True).exists():
                partner = AffiliatePartner.objects.filter(code=code, status="approved", user__is_active=True).exclude(user=user).first()
                if partner:
                    AffiliateReferral.objects.create(partner=partner, user=user)
    if allow_referral:
        request.session.pop("ptjc_affiliate_code", None)
        request.session.pop("ptjc_affiliate_at", None)
    return user


@require_http_methods(["GET"])
def affiliate_link(request, code):
    get_object_or_404(AffiliateProgram, pk=1, enabled=True)
    get_object_or_404(AffiliatePartner, code=code, status="approved", user__is_active=True)
    if not request.user.is_authenticated:
        request.session["ptjc_affiliate_code"] = code
        request.session["ptjc_affiliate_at"] = int(timezone.now().timestamp())
    return redirect("employer_signup")


class PartnerApplication(forms.Form):
    website = forms.URLField(required=False)
    accept = forms.BooleanField(label="I accept the affiliate program terms")


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def affiliate_apply(request):
    import secrets
    program = get_object_or_404(AffiliateProgram, pk=1, enabled=True)
    partner = AffiliatePartner.objects.filter(user=request.user).first()
    form = PartnerApplication(request.POST if request.method == "POST" else None)
    if not partner and request.method == "POST" and program.applications_open and program.terms.strip() and form.is_valid():
        AffiliatePartner.objects.get_or_create(user=request.user, defaults={"code": secrets.token_hex(12),
            "website": form.cleaned_data["website"], "terms_accepted_at": timezone.now()})
        return redirect("affiliate_apply")
    return render(request, "board/affiliate_apply.html", {"program": program, "partner": partner, "form": form})
