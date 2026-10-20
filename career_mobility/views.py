from django.views.decorators.http import require_POST
from decimal import Decimal
from django.contrib.auth import login
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from .forms import InternationalSignupForm
from .models import InternationalProfile,PathwayRule,ReferenceCost,DigitalProduct,ProductOrder

def home(request):
    return render(request,"career_mobility/home.html")

from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse

@staff_member_required
def shop_admin(request):
    from django.db.models import Sum
    latest_products = DigitalProduct.objects.order_by('-pk')[:8]
    recent_orders = ProductOrder.objects.select_related('user', 'product').order_by('-created_at')[:8]
    revenue = ProductOrder.objects.filter(paid=True).aggregate(total=Sum('product__price_cad'))['total'] or Decimal('0')
    return render(request, 'career_mobility/shop_admin.html', {
        'latest_products': latest_products, 'recent_orders': recent_orders, 'revenue_estimate': revenue,
        'published': DigitalProduct.objects.filter(is_published=True).count(),
        'drafts': DigitalProduct.objects.filter(is_published=False).count(),
        'orders': ProductOrder.objects.count(),
        'sources_pending': __import__('career_mobility.models',fromlist=['DataSourceReview']).DataSourceReview.objects.filter(status='pending').count(),
        'fees_pending': __import__('career_mobility.models',fromlist=['ProvincialLicenceFee']).ProvincialLicenceFee.objects.filter(is_published=False).count(),
        'salary_regions': __import__('career_mobility.models',fromlist=['SalaryBenchmark']).SalaryBenchmark.objects.filter(is_published=True).count(),
        'international_profiles': InternationalProfile.objects.count(),
        'saved_plans': __import__('career_mobility.models',fromlist=['SavedCareerPlan']).SavedCareerPlan.objects.count(),
        'products_missing_files': DigitalProduct.objects.filter(download='').count(),
        'paid_orders': ProductOrder.objects.filter(paid=True).count(),
    })

def shop(request):
    """Public catalogue, shared by future resume/template and pathway products."""
    products = DigitalProduct.objects.filter(is_published=True).order_by('title')
    owned = set()
    if request.user.is_authenticated:
        owned = set(ProductOrder.objects.filter(user=request.user, paid=True).values_list('product_id', flat=True))
    return render(request, 'career_mobility/shop.html', {'products': products, 'owned_ids': owned})

def international(request):
    countries=PathwayRule.objects.filter(is_published=True)
    country=request.GET.get("country","")
    rule=countries.filter(country__iexact=country).first() if country else None
    from .forms import PROVINCES
    from .research import research_context
    return render(request,"career_mobility/international.html",{"countries":countries,"rule":rule,"country":country,"provinces":PROVINCES,"research":research_context()})

def signup(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "international_pt_profile"):
            return redirect("mobility_international_dashboard")
        from django.contrib.auth import logout
        if request.method == "POST":
            return HttpResponseForbidden("Sign out of your existing account before creating a separate international PT account.")
        return render(request, "career_mobility/signup_account_conflict.html")
    initial = {key:request.GET.get(key, "")[:100] for key in ("country_of_education", "citizenship_country", "destination_province", "registered_in_education_country")}
    form=InternationalSignupForm(request.POST or None, initial=initial)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            user=form.save()
        login(request,user)
        return redirect("mobility_international_dashboard")
    from .forms import COUNTRIES
    return render(request,"career_mobility/signup.html",{"form":form,"country_options":COUNTRIES})

@login_required
def dashboard(request):
    profile=getattr(request.user,"international_pt_profile",None)
    if profile is None: return HttpResponseForbidden("International PT account required.")
    products=DigitalProduct.objects.filter(is_published=True).order_by("title")
    completed=set(profile.checklist_items.filter(completed=True).values_list("key",flat=True))
    checklist=[{"key":key,"label":label,"completed":key in completed} for key,label in CHECKLIST]
    fees=ProvincialLicenceFee.objects.filter(is_published=True,province=profile.destination_province).order_by("fee_type")
    rule=PathwayRule.objects.filter(country__iexact=profile.country_of_education,is_published=True).first()
    paid_ids=set(ProductOrder.objects.filter(user=request.user,paid=True).values_list("product_id",flat=True))
    from .forms import InternationalProfileUpdateForm
    profile_form = InternationalProfileUpdateForm(instance=profile)
    completed_count = len(completed)
    return render(request,"career_mobility/dashboard.html",{"profile":profile,"products":products,"checklist":checklist,"fees":fees,"rule":rule,"paid_ids":paid_ids,"owned_products":products.filter(pk__in=paid_ids),"available_products":products.exclude(pk__in=paid_ids),"completed_count":completed_count,"total_count":len(CHECKLIST),"progress":round(100*completed_count/len(CHECKLIST)),"profile_form":profile_form,"salary_plans":SavedCareerPlan.objects.filter(user=request.user,plan_type="salary")[:5]})

def _canadian_context():
    costs=ReferenceCost.objects.filter(is_published=True).order_by("province","city","kind")
    rows={}
    citations={}
    for c in costs:
        key=f"{c.city}, {c.province}" if c.city else c.province
        rows.setdefault(key,{})[c.kind]=str(c.amount_cad)
        citations.setdefault(key,{})[c.kind]={"url":c.source_url,"verified":c.verified_on.isoformat() if c.verified_on else "Unverified"}
    fees=ProvincialLicenceFee.objects.filter(is_published=True).order_by("province","fee_type")
    from .research import research_context
    research = research_context()
    for item in research["locations"]:
        if item["rent"] is None:
            continue
        key = f'{item["city"]}, {item["province"]}'
        # Published database entries are retained; snapshots fill missing references only.
        rows.setdefault(key, {}).setdefault("rent", str(item["rent"]))
        citations.setdefault(key, {}).setdefault("rent", {"url":item["source_url"], "verified":item["verified_on"], "period":item["reference_period"], "basis":item["basis"]})
    return {"costs":rows,"citations":citations,"fees":fees,"research":research}

def canadian(request):
    return render(request, "career_mobility/canadian_basic.html", _canadian_context())

@login_required
def relocation_comparisons(request):
    """Private, multi-destination planning workspace; never exposes other users' data."""
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return HttpResponseForbidden("A Canadian job seeker account is required.")
    from decimal import Decimal, InvalidOperation
    from .models import SavedCareerPlan
    plans = SavedCareerPlan.objects.filter(user=request.user, plan_type="relocation").order_by("-created_at")[:50]
    def num(value):
        try:
            n = Decimal(str(value))
            return n if n.is_finite() and n >= 0 and n <= Decimal("100000000") else None
        except (InvalidOperation, ValueError, TypeError):
            return None
    comparisons = []
    for plan in plans:
        data = plan.inputs if isinstance(plan.inputs, dict) else {}
        keys = ("current-salary", "new-salary", "current-rent", "new-rent", "current-living", "new-living")
        values = [num(data.get(key)) for key in keys]
        if data.get("expense_mode") == "itemized":
            for index, side in [(4, "current"), (5, "new")]:
                costs = [num(data.get(side+"-"+kind) or 0) for kind in ("utilities", "transport", "groceries", "childcare", "extra")]
                values[index] = sum(costs, Decimal(0)) if all(c is not None for c in costs) else None
        takehome = [num(data.get(key)) for key in ("current-net", "new-net")]
        income = takehome if all(n is not None for n in takehome) else [n/12 if n is not None else None for n in values[:2]]
        difference = None
        if all(x is not None for x in values):
            a, b, ar, br, al, bl = values
            difference = income[1]-income[0] - (br-ar) - (bl-al)
        comparisons.append({"plan": plan, "origin": str(data.get("origin") or "Not specified")[:90],
            "destination": str(data.get("destination") or "Not specified")[:90],
            "difference": difference, "new_salary": num(data.get("new-salary")),
            "new_rent": num(data.get("new-rent")), "new_living": values[5],
            "monthly_budget": (income[1]-values[3]-values[5]) if all(values[i] is not None for i in (1,3,5)) else None})
    valid = [row for row in comparisons if row["difference"] is not None]
    best = max(valid, key=lambda row: row["difference"]) if valid else None
    return render(request, "career_mobility/relocation_comparisons.html", {
        "comparisons": comparisons, "best": best, "scenario_count": len(comparisons),
        "complete_count": len(valid),
    })

@login_required
@require_POST
def rename_relocation_plan(request, pk):
    """Rename a candidate's own saved scenario; other candidates' plans remain inaccessible."""
    from .models import SavedCareerPlan
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return HttpResponseForbidden("A Canadian job seeker account is required.")
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user, plan_type="relocation")
    title = " ".join(request.POST.get("title", "").split())[:120]
    if title:
        plan.title = title
        plan.save(update_fields=["title"])
    return redirect("mobility_relocation_comparisons")

@login_required
def canadian_full(request):
    if hasattr(request.user,"international_pt_profile") or not getattr(getattr(request.user,"jobseeker",None),"is_approved",False):
        return HttpResponseForbidden("Registered Canadian job seeker account required.")
    context = _canadian_context()
    if request.GET.get("saved"):
        plan = get_object_or_404(SavedCareerPlan, pk=request.GET["saved"], user=request.user, plan_type="relocation")
        context["saved_inputs"] = plan.inputs
    return render(request, "career_mobility/canadian.html", context)

@login_required
def product_download(request,pk):
    product=get_object_or_404(DigitalProduct,pk=pk,is_published=True)
    if not ProductOrder.objects.filter(user=request.user,product=product,paid=True).exists():
        return HttpResponseForbidden("Purchase required.")
    if not product.download: raise Http404()
    # Do not redirect to a public storage URL: protected downloads need private storage.
    from django.http import FileResponse
    response=FileResponse(product.download.open("rb"),as_attachment=True,filename=product.download.name.rsplit("/",1)[-1])
    response["Cache-Control"]="private, no-store"
    return response


from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import (InternationalChecklistItem, SavedCareerPlan, SalaryBenchmark,
                     ProvincialLicenceFee)

CHECKLIST = [
    ("education", "Confirm education jurisdiction and CAPR pathway"),
    ("capr", "Review current CAPR requirements and document submission rules"),
    ("language", "Check accepted language evidence and exemptions"),
    ("documents", "Request official transcripts and required school documents"),
    ("professional", "Confirm registration or good-standing documentation if applicable"),
    ("assessment", "Budget for CAPR credentialling and assessment stages"),
    ("province", "Review your destination province's regulator requirements"),
    ("fees", "Confirm provincial application, examination and registration fees"),
    ("immigration", "Review IRCC immigration/work authorization requirements separately"),
    ("apply", "Submit applications through official organizations only"),
]

def salary_comparison(request):
    benchmarks = SalaryBenchmark.objects.filter(is_published=True).order_by("region")
    return render(request, "career_mobility/salary_comparison.html", {"benchmarks": benchmarks})

@require_POST
@login_required
def save_plan(request):
    """Legacy endpoint: Canadian planning only; salary uses the canonical validator."""
    import json
    from django.http import JsonResponse
    international = hasattr(request.user, "international_pt_profile")
    canadian = bool(getattr(getattr(request.user, "jobseeker", None), "is_approved", False))
    if international or not canadian:
        return HttpResponseForbidden("A PTJC candidate account is required.")
    try:
        payload = json.loads(request.body)
        plan_type = payload["plan_type"]
        if plan_type == "salary":
            from .salary_save import save_salary_comparison
            return save_salary_comparison(request)
        inputs = payload["inputs"]
        if plan_type not in ("salary", "relocation") or (international and not canadian and plan_type != "salary"):
            return HttpResponseForbidden("This comparison is not available for your account type.")
        if not isinstance(inputs, dict) or len(json.dumps(inputs)) > 6000 or not inputs:
            raise ValueError("Invalid plan")
        if not all(isinstance(k, str) and isinstance(v, (str, int, float, bool, type(None))) for k, v in inputs.items()):
            raise ValueError("Invalid plan fields")
        plan = SavedCareerPlan.objects.create(user=request.user, plan_type=plan_type,
            title=str(payload.get("title") or "My comparison")[:120], inputs=inputs)
        return JsonResponse({"id": plan.pk, "saved": True, "url": reverse("mobility_my_plans")})
    except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid plan data"}, status=400)

@login_required
def my_plans(request):
    if not (hasattr(request.user, "jobseeker") or hasattr(request.user, "international_pt_profile")):
        return HttpResponseForbidden("A PTJC candidate account is required.")
    return render(request, "career_mobility/my_plans.html", {"plans": SavedCareerPlan.objects.filter(user=request.user).order_by("-created_at")[:50]})

@login_required
@require_POST
def delete_plan(request, pk):
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user)
    plan.delete()
    return redirect("mobility_my_plans")

@login_required
def plan_pdf(request, pk):
    """Private, simple report for an existing saved comparison; never expose another user's data."""
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user)
    if plan.plan_type == "salary":
        from .salary_report import pdf_bytes
        try:
            report=pdf_bytes(plan.inputs, plan.title)
        except (ValueError, TypeError, KeyError, OverflowError):
            return HttpResponse("This saved comparison has invalid values.",status=400)
        response=HttpResponse(report,content_type="application/pdf")
        response["Content-Disposition"]='attachment; filename="ptjc-salary-comparison.pdf"'
        response["Cache-Control"]="private, no-store"
        return response

    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, title="PTJC saved comparison")
    styles = getSampleStyleSheet()
    rows = [["Field", "Value"]]
    for key, value in sorted(plan.inputs.items()):
        label = str(key).replace("_", " ").title()[:70]
        rows.append([Paragraph(escape(label), styles["Normal"]), Paragraph(escape(str(value)[:180]), styles["Normal"])])
    table = Table(rows, colWidths=[190, 310], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f1f2")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8e2e8")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    doc.build([Paragraph(escape(plan.title), styles["Title"]), Paragraph(f"Saved {plan.created_at:%Y-%m-%d}", styles["Normal"]), Spacer(1, 18), table, Spacer(1, 16), Paragraph("Personal planning record. Gross figures are not take-home income; contractor income is before expenses and taxes. Verify all offer terms independently.", styles["Italic"])])
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ptjc-comparison-{plan.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response

@login_required
@require_POST
def checklist_toggle(request):
    profile = getattr(request.user, "international_pt_profile", None)
    if profile is None:
        return HttpResponseForbidden("International account required.")
    key = request.POST.get("key", "")
    if key not in dict(CHECKLIST):
        return HttpResponse(status=400)
    item, _ = InternationalChecklistItem.objects.get_or_create(profile=profile, key=key)
    item.completed = not item.completed
    item.save(update_fields=["completed", "updated_at"])
    return redirect("mobility_international_dashboard")

@login_required
def personalized_checklist(request):
    profile = getattr(request.user, "international_pt_profile", None)
    if profile is None:
        return HttpResponseForbidden("International account required.")
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from xml.sax.saxutils import escape
    buf = BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    elements = [Paragraph("International PT pathway checklist", styles["Title"]), Spacer(1, 12)]
    for label, val in [("Education country", profile.country_of_education), ("Citizenship", profile.citizenship_country), ("Residence", profile.residence_country), ("Destination province", profile.destination_province or "Not selected")]:
        elements.append(Paragraph(f"<b>{escape(label)}:</b> {escape(val or 'Not supplied')}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    done = set(profile.checklist_items.filter(completed=True).values_list("key", flat=True))
    for key, label in CHECKLIST:
        elements.append(Paragraph(f"{'DONE' if key in done else 'TO DO'} - {escape(label)}", styles["Normal"]))
        elements.append(Spacer(1, 7))
    elements.append(Spacer(1, 12))
    for text, url in [("CAPR", "https://alliancept.org/"), ("Immigration, Refugees and Citizenship Canada", "https://www.canada.ca/en/immigration-refugees-citizenship.html")]:
        elements.append(Paragraph(f"{escape(text)}: {escape(url)}", styles["Normal"]))
    elements.append(Paragraph("Planning aid only. Requirements and fees depend on your application date and regulator. Check official sources before paying or applying.", styles["Italic"]))
    doc.build(elements)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="international-pt-checklist.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response

@login_required
def product_checkout(request, pk):
    if request.method != "POST":
        return HttpResponse(status=405)
    product = get_object_or_404(DigitalProduct, pk=pk, is_published=True)
    if ProductOrder.objects.filter(user=request.user, product=product, paid=True).exists():
        return redirect("mobility_international_dashboard") if hasattr(request.user, "international_pt_profile") else redirect("mobility_shop")
    if not product.download or product.price_cad <= 0:
        return HttpResponse(status=400)
    import os
    secret = os.environ.get("PT_MOBILITY_STRIPE_SECRET_KEY", "")
    webhook = os.environ.get("PT_MOBILITY_STRIPE_WEBHOOK_SECRET", "")
    if not secret or not webhook:
        return HttpResponse("Digital checkout is not configured", status=503)
    import stripe
    stripe.api_key = secret
    base = request.build_absolute_uri("/").rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="payment", client_reference_id=str(request.user.pk),
            line_items=[{"price_data": {"currency": "cad", "unit_amount": int(product.price_cad * 100),
                "product_data": {"name": product.title}}, "quantity": 1}],
            success_url=base + ("/career-resources/international/dashboard/?payment=return" if hasattr(request.user, "international_pt_profile") else "/shop/?payment=return"),
            cancel_url=base + ("/career-resources/international/dashboard/?payment=cancel" if hasattr(request.user, "international_pt_profile") else "/shop/?payment=cancel"),
            metadata={"mobility_product_id": str(product.pk), "mobility_user_id": str(request.user.pk)},
        )
    except stripe.error.StripeError:
        return HttpResponse("Payment provider unavailable", status=503)
    ProductOrder.objects.get_or_create(stripe_session_id=session.id, defaults={"user": request.user, "product": product, "paid": False})
    return redirect(session.url)

@csrf_exempt
def mobility_stripe_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    import os
    secret = os.environ.get("PT_MOBILITY_STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return HttpResponse(status=503)
    import stripe
    try:
        event = stripe.Webhook.construct_event(request.body, request.META.get("HTTP_STRIPE_SIGNATURE", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        obj = event["data"]["object"]
        if obj.get("payment_status") == "paid":
            ProductOrder.objects.filter(stripe_session_id=obj["id"], paid=False).update(paid=True)
    return HttpResponse(status=200)


def clinic_offer_guide(request):
    """Free educational companion to the public salary comparison tool."""
    return render(request, "career_mobility/clinic_offer_guide.html")


@require_POST
def salary_comparison_pdf(request):
    """Generate a private report; do not trust client-calculated totals."""
    import json
    from django.http import HttpResponse, JsonResponse
    from .salary_report import pdf_bytes
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload=json.loads(request.body)
        result=pdf_bytes(payload)
    except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError):
        return JsonResponse({"error": "Enter valid values for both offers."}, status=400)
    response=HttpResponse(result,content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="ptjc-salary-vs-split.pdf"'
    response["Cache-Control"]="private, no-store"
    return response

@login_required
@require_POST
def update_international_profile(request):
    """Update only the signed-in international PT's own planning details."""
    from .forms import InternationalProfileUpdateForm
    profile = getattr(request.user, "international_pt_profile", None)
    if profile is None:
        return HttpResponseForbidden("International PT account required.")
    form = InternationalProfileUpdateForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        messages.success(request, "Your planning details were updated.")
        return redirect("mobility_international_dashboard")
    completed = set(profile.checklist_items.filter(completed=True).values_list("key", flat=True))
    checklist = [{"key":key,"label":label,"completed":key in completed} for key,label in CHECKLIST]
    return render(request,"career_mobility/dashboard.html",{"profile":profile,"profile_form":form,"checklist":checklist,"completed_count":len(completed),"total_count":len(CHECKLIST),"progress":round(100*len(completed)/len(CHECKLIST)),"products":DigitalProduct.objects.filter(is_published=True),"fees":ProvincialLicenceFee.objects.none(),"salary_plans":[],"paid_ids":set() },status=400)
