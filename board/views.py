from __future__ import annotations

import json
from datetime import timedelta, date
from typing import Optional, List

import requests
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db.models import Q, F, Sum
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

# Stripe is optional; if not installed you can comment this import and the stripe usage.
import stripe

from .forms import JobForm, EmployerSignUpForm, JobSeekerSignUpForm
from .models import (
    Employer,
    JobSeeker,
    Job,
    JobAlert,
    PostingPackage,
    PurchasedPackage,
    Resume,
    Application,
    SavedJob,
    EmailTemplate,
    Invoice,
)

# Optional models (present if you added them)
try:
    from .models import DiscountCode, PaymentGatewayConfig  # type: ignore
except Exception:  # pragma: no cover
    DiscountCode = None  # type: ignore
    PaymentGatewayConfig = None  # type: ignore


# ----------------- Small helpers -----------------
def _unique_username_from_email(email: str) -> str:
    base = (email or "user").split("@")[0][:30] or "user"
    cand = base
    i = 1
    while User.objects.filter(username=cand).exists():
        cand = f"{base}{i}"
        i += 1
    return cand


def _require_employer(request) -> Optional[Employer]:
    if not request.user.is_authenticated or not hasattr(request.user, "employer"):
        messages.error(request, "Please log in as an employer.")
        return None
    emp = request.user.employer
    if not emp.is_approved:
        messages.warning(request, "Your employer account is pending approval.")
    return emp


def _require_jobseeker(request) -> Optional[JobSeeker]:
    if not request.user.is_authenticated or not hasattr(request.user, "jobseeker"):
        messages.error(request, "Please log in as a job seeker.")
        return None
    js = request.user.jobseeker
    if not js.is_approved:
        messages.warning(request, "Your job seeker account is pending approval.")
    return js


def _render_email_template(slug: str, fallback_subject: str, fallback_body: str, context: dict) -> tuple[str, str]:
    try:
        tpl = EmailTemplate.objects.filter(slug=slug, is_active=True).first()
        if tpl:
            return tpl.subject.format(**context), tpl.body.format(**context)
    except Exception:
        pass
    return fallback_subject.format(**context), fallback_body.format(**context)


def _get_gateway_keys() -> tuple[str, str]:
    """Stripe keys, preferring active PaymentGatewayConfig if present."""
    if PaymentGatewayConfig:
        try:
            cfg = PaymentGatewayConfig.get_active_gateway()
            if cfg and getattr(cfg, "use_stripe", False) and cfg.stripe_secret_key and cfg.stripe_public_key:
                return cfg.stripe_public_key, cfg.stripe_secret_key
        except Exception:
            pass
    return getattr(settings, "STRIPE_PUBLIC_KEY", ""), getattr(settings, "STRIPE_SECRET_KEY", "")


def _get_active_paypal():
    """Return (base_url, client_id, client_secret) from active PaymentGatewayConfig; empty strings if not configured."""
    if not PaymentGatewayConfig:
        return "", "", ""
    cfg = PaymentGatewayConfig.get_active_gateway()
    if not cfg or not getattr(cfg, "use_paypal", False) or not cfg.paypal_client_id or not cfg.paypal_client_secret:
        return "", "", ""
    mode = getattr(cfg, "paypal_mode", "sandbox") or "sandbox"
    base = "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"
    return base, cfg.paypal_client_id, cfg.paypal_client_secret


def _paypal_access_token(base_url: str, client_id: str, client_secret: str) -> Optional[str]:
    try:
        resp = requests.post(
            f"{base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception:
        pass
    return None


def _apply_discount_if_any(price_cents: int, discount_code: str) -> int:
    if not discount_code or not DiscountCode:
        return price_cents
    dc = DiscountCode.objects.filter(code__iexact=discount_code).first()
    if not dc or not dc.is_valid_now():
        return price_cents
    try:
        return dc.apply_to_cents(price_cents)
    except Exception:
        return price_cents


def _increment_discount_use(discount_code: str):
    if DiscountCode and discount_code:
        try:
            dc = DiscountCode.objects.filter(code__iexact=discount_code).first()
            if dc and dc.is_valid_now():
                dc.uses = (dc.uses or 0) + 1
                dc.save(update_fields=["uses"])
        except Exception:
            pass


def _default_purchase_expiry_days() -> int:
    return int(getattr(settings, "PURCHASE_EXPIRY_DAYS_DEFAULT", 365) or 365)


# ----------------- Public views -----------------
def home(request):
    latest_jobs = Job.objects.filter(is_active=True).order_by("-posting_date")[:10]
    featured_jobs = Job.objects.filter(is_active=True, featured=True).order_by("-posting_date")[:5]
    return render(request, "board/homepage.html", {"latest_jobs": latest_jobs, "featured_jobs": featured_jobs})


def job_list(request):
    qs = Job.objects.filter(is_active=True)
    q = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if location:
        qs = qs.filter(location__icontains=location)
    qs = qs.order_by("-posting_date")
    return render(request, "board/job_list.html", {"jobs": qs, "q": q, "location": location})


def job_detail(request, pk: int):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    return render(request, "board/job_detail.html", {"job": job})


# ----------------- Apply / Save / Unsave -----------------
@login_required
def job_apply(request, pk: int):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")

    class ApplyForm(forms.Form):
        name = forms.CharField(
            max_length=255,
            initial=getattr(js, "full_name", js.user.get_full_name() or js.user.username),
            widget=forms.TextInput(attrs={"class": "form-control"}),
        )
        email = forms.EmailField(
            initial=js.user.email or getattr(js, "email", ""),
            widget=forms.EmailInput(attrs={"class": "form-control"}),
        )
        resume_id = forms.ChoiceField(
            choices=[("", "Select a resume")] + [(str(r.id), r.file.name.split("/")[-1]) for r in js.resumes.all()],
            required=False,
            widget=forms.Select(attrs={"class": "form-select"}),
        )
        cover_letter = forms.CharField(
            required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 5})
        )

    if request.method == "POST":
        form = ApplyForm(request.POST, request.FILES)
        if form.is_valid():
            app = Application.objects.create(
                job=job,
                jobseeker=js,
                cover_letter=form.cleaned_data.get("cover_letter", ""),
            )
            resume_id = form.cleaned_data.get("resume_id")
            if resume_id:
                try:
                    r = js.resumes.get(id=resume_id)
                    app.resume.save(r.file.name.split("/")[-1], r.file.file, save=True)
                except Exception:
                    pass
            elif getattr(js, "resume", None):
                try:
                    app.resume.save(js.resume.name.split("/")[-1], js.resume.file, save=True)
                except Exception:
                    pass

            to_email = job.application_email or job.employer.user.email or getattr(job.employer, "email", "")
            context = {
                "job_title": job.title,
                "employer_name": job.employer.company_name or job.employer.user.get_full_name() or job.employer.user.username,
                "applicant_name": form.cleaned_data["name"],
                "applicant_email": form.cleaned_data["email"],
                "cover_letter": form.cleaned_data.get("cover_letter", ""),
                "employer_dashboard_url": request.build_absolute_uri(reverse("employer_dashboard")),
            }
            subject, body = _render_email_template(
                "application_email_to_employer",
                fallback_subject="New application for {job_title}",
                fallback_body=(
                    "Hello,\n\n"
                    "You received a new application to your job posting {job_title} from the following applicant:\n\n"
                    "Name: {applicant_name}\n"
                    "Email: {applicant_email}\n\n"
                    "Cover Letter:\n{cover_letter}\n\n"
                    "View all applications: {employer_dashboard_url}\n\n"
                    "Thanks,\nThe PhysiotherapyJobsCanada team"
                ),
                context=context,
            )
            if to_email:
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
                    to=[to_email],
                )
                if app.resume:
                    try:
                        email.attach(app.resume.name.split("/")[-1], app.resume.read())
                    except Exception:
                        pass
                try:
                    email.send(fail_silently=True)
                except Exception:
                    pass

            messages.success(request, "Thank you! Your application has been sent.")
            return redirect("job_detail", pk=job.pk)
    else:
        form = ApplyForm()

    return render(request, "board/job_apply.html", {"form": form, "job": job})


@login_required
def save_job(request, pk: int):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")
    SavedJob.objects.get_or_create(jobseeker=js, job=job)
    messages.success(request, "Job saved.")
    return redirect("job_detail", pk=pk)


@login_required
def unsave_job(request, pk: int):
    job = get_object_or_404(Job, pk=pk)
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")
    SavedJob.objects.filter(jobseeker=js, job=job).delete()
    messages.info(request, "Job removed from saved.")
    return redirect("job_detail", pk=pk)


# ----------------- Employers (public) -----------------
def employer_list(request):
    employers = Employer.objects.filter(is_approved=True).order_by("company_name", "user__username")
    employers = [e for e in employers if e.jobs.filter(is_active=True).exists()]
    return render(request, "board/employer_list.html", {"employers": employers})


def employer_public_profile(request, pk: int):
    employer = get_object_or_404(Employer, pk=pk, is_approved=True)
    open_jobs = employer.jobs.filter(is_active=True).order_by("-posting_date", "-id")
    return render(request, "board/employer_profile.html", {"employer": employer, "open_jobs": open_jobs})


# ----------------- Packages / checkout -----------------
def package_list(request):
    packages = PostingPackage.objects.filter(is_active=True).order_by("order", "name")
    return render(request, "packages/package_list.html", {"packages": packages})


def checkout_start(request, code):
    """Stripe Checkout (kept as-is). Discount via ?discount=CODE."""
    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)

    discount_code = (request.GET.get("discount") or "").strip()
    price_cents = int(pkg.price_cents or 0)
    price_cents = _apply_discount_if_any(price_cents, discount_code)

    pub, secret = _get_gateway_keys()
    if not secret or "sk_test_123" in secret:
        messages.error(request, "Stripe is not configured yet. Set keys in Admin → Payment Gateway Config.")
        return redirect("package_list")

    try:
        stripe.api_key = secret
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {"name": pkg.name},
                        "unit_amount": price_cents,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=request.build_absolute_uri(reverse("package_list")) + "?success=1",
            cancel_url=request.build_absolute_uri(reverse("package_list")) + "?canceled=1",
        )
        return redirect(session.url, code=303)
    except Exception as e:
        messages.error(request, f"Checkout error: {e}")
        return redirect("package_list")


# ----------------- PayPal (server-side) -----------------
@login_required
def checkout_paypal(request, code):
    """
    Render PayPal Smart Buttons page; buttons will call our server endpoints
    to create and capture the order. Requires employer login to tie purchase.
    """
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)
    discount_code = (request.GET.get("discount") or "").strip()

    # Compute final price
    price_cents = int(pkg.price_cents or 0)
    price_cents = _apply_discount_if_any(price_cents, discount_code)
    price_display = f"{price_cents/100:.2f}"

    base, client_id, client_secret = _get_active_paypal()
    if not client_id or not client_secret:
        messages.error(request, "PayPal is not configured yet. Set keys in Admin → Payment Gateway Config.")
        return redirect("package_list")

    # Keep needed info for later capture verification
    request.session["paypal_expected"] = {
        "code": pkg.code,
        "price_cents": price_cents,
        "discount": discount_code,
    }

    return render(
        request,
        "packages/checkout_paypal.html",
        {
            "package": pkg,
            "discount_code": discount_code,
            "price_cents": price_cents,
            "price_display": price_display,
            "paypal_client_id": client_id,  # For the SDK script tag
        },
    )


@login_required
def paypal_create_order(request, code):
    """
    Server-side creates a PayPal order for the expected amount.
    Returns JSON {id: "..."} for the JS Buttons createOrder handler.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    emp = _require_employer(request)
    if emp is None:
        return HttpResponseForbidden("Employer required")

    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)

    sess = request.session.get("paypal_expected") or {}
    # Trust the server-side computation; if missing, recompute.
    price_cents = int(sess.get("price_cents") or 0)
    discount_code = (sess.get("discount") or "").strip()
    if price_cents <= 0 or sess.get("code") != pkg.code:
        discount_code = (request.GET.get("discount") or "").strip()
        price_cents = int(pkg.price_cents or 0)
        price_cents = _apply_discount_if_any(price_cents, discount_code)

    amount_value = f"{price_cents/100:.2f}"

    base, client_id, client_secret = _get_active_paypal()
    token = _paypal_access_token(base, client_id, client_secret)
    if not token:
        return JsonResponse({"error": "paypal_auth_failed"}, status=400)

    try:
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "description": f"{pkg.name}",
                    "amount": {"currency_code": "CAD", "value": amount_value},
                }
            ],
            "application_context": {
                "shipping_preference": "NO_SHIPPING",
                "brand_name": "PT Jobs",
                "user_action": "PAY_NOW",
                # Return URLs not used by Smart Buttons; we capture via API
            },
        }
        resp = requests.post(
            f"{base}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=20,
        )
        data = resp.json()
        if resp.status_code not in (201, 200) or not data.get("id"):
            return JsonResponse({"error": "create_failed", "details": data}, status=400)
        # Stash mapping for capture validation
        request.session[f"paypal_map_{data['id']}"] = {
            "code": pkg.code,
            "price_cents": price_cents,
            "discount": discount_code,
        }
        return JsonResponse({"id": data["id"]})
    except Exception as e:
        return JsonResponse({"error": "exception", "details": str(e)}, status=400)


@login_required
def paypal_capture_order(request, code):
    """
    Server-side capture; on success, grant credits (PurchasedPackage),
    create an Invoice, and return JSON status.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    emp = _require_employer(request)
    if emp is None:
        return HttpResponseForbidden("Employer required")

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = {}
    order_id = (body.get("order_id") or "").strip()
    if not order_id:
        return JsonResponse({"error": "missing_order_id"}, status=400)

    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)

    base, client_id, client_secret = _get_active_paypal()
    token = _paypal_access_token(base, client_id, client_secret)
    if not token:
        return JsonResponse({"error": "paypal_auth_failed"}, status=400)

    # Capture
    try:
        resp = requests.post(
            f"{base}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=25,
        )
        data = resp.json()
    except Exception as e:
        return JsonResponse({"error": "exception", "details": str(e)}, status=400)

    status = (data.get("status") or "").upper()
    if status != "COMPLETED":
        return JsonResponse({"error": "not_completed", "status": status, "details": data}, status=400)

    # Validate amount vs our expected amount
    mapping = request.session.get(f"paypal_map_{order_id}") or request.session.get("paypal_expected") or {}
    expected_cents = int(mapping.get("price_cents") or 0)
    expected_code = mapping.get("code")
    discount_code = (mapping.get("discount") or "").strip()

    # Pull the first capture amount
    try:
        purchase_units = data["purchase_units"]
        payments = purchase_units[0]["payments"]
        captures = payments["captures"]
        capture = captures[0]
        amt_val = capture["amount"]["value"]  # string like "24.90"
        currency = capture["amount"]["currency_code"]
    except Exception:
        return JsonResponse({"error": "parse_capture"}, status=400)

    if currency != "CAD":
        return JsonResponse({"error": "currency_mismatch", "currency": currency}, status=400)

    amount_cents_captured = int(round(float(amt_val) * 100))
    if expected_cents and amount_cents_captured != expected_cents:
        return JsonResponse(
            {"error": "amount_mismatch", "expected_cents": expected_cents, "captured_cents": amount_cents_captured},
            status=400,
        )

    # Grant credits
    try:
        credits_total = int(getattr(pkg, "max_jobs", 0) or 0) or 1
        purchased_at = timezone.now()
        expiry_days = _default_purchase_expiry_days()
        expires_at = purchased_at.date() + timedelta(days=expiry_days)

        PurchasedPackage.objects.create(
            employer=emp,
            package=pkg,
            credits_total=credits_total,
            credits_used=0,
            purchased_at=purchased_at,
            expires_at=expires_at,
        )
    except Exception:
        # Don’t fail the response if credits creation has issues; report partial success
        pass

    # Create an invoice record if the model supports these fields
    try:
        Invoice.objects.create(
            employer=emp,
            amount_cents=amount_cents_captured,
            notes=f"PayPal {order_id} · {pkg.name} ({pkg.code})",
        )
    except Exception:
        pass

    # Increment discount usage if any
    _increment_discount_use(discount_code)

    # Success
    return JsonResponse({"status": "COMPLETED"})
# ----------------- End PayPal -----------------


# ----------------- Signups -----------------
def employer_signup(request):
    if request.method == "POST":
        form = EmployerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            username = _unique_username_from_email(email)
            # Employer user is inactive until approved -> cannot log in
            user = User.objects.create_user(username=username, email=email, password=password, is_active=False)

            Employer.objects.create(
                user=user,
                email=email,
                name=form.cleaned_data["contact_name"],
                company_name=form.cleaned_data.get("company_name", ""),
                phone=form.cleaned_data.get("contact_phone", ""),
                website=form.cleaned_data.get("website", ""),
                location=form.cleaned_data["location"],
                logo=form.cleaned_data.get("logo"),
                description=form.cleaned_data.get("description", ""),
                is_approved=False,
            )

            messages.success(
                request,
                "Thanks! Your employer account is pending approval. You’ll be able to log in once approved."
            )
            return redirect("home")
    else:
        form = EmployerSignUpForm()
    return render(request, "board/employer_signup.html", {"form": form})


def jobseeker_signup(request):
    if request.method == "POST":
        form = JobSeekerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            username = _unique_username_from_email(email)
            user = User.objects.create_user(username=username, email=email, password=password)

            opp_type = form.cleaned_data.get("opportunity_type", "")
            pos_desired = form.cleaned_data.get("position_desired", "")

            JobSeeker.objects.create(
                user=user,
                email=email,
                first_name=form.cleaned_data.get("first_name", ""),
                last_name=form.cleaned_data.get("last_name", ""),
                current_location=form.cleaned_data.get("current_location", ""),
                position_desired=pos_desired,
                opportunity_type=opp_type,
                registration_status=form.cleaned_data["registration_status"],
                open_to_relocation=form.cleaned_data["open_to_relocation"],
                relocation_where=form.cleaned_data.get("relocation_where", ""),
                need_sponsorship=form.cleaned_data["need_sponsorship"],
                seeking_immigration=form.cleaned_data["seeking_immigration"],
                resume=form.cleaned_data.get("resume"),
                is_approved=False,
            )

            messages.success(request, "Account created. An admin will review and approve your job seeker profile.")
            return redirect("home")
    else:
        form = JobSeekerSignUpForm()
    return render(request, "board/jobseeker_signup.html", {"form": form})


def job_alert_signup(request):
    if request.method != "POST":
        return redirect("home")

    email = (request.POST.get("email") or "").strip()
    q = (request.POST.get("q") or request.POST.get("keywords") or "").strip()
    location = (request.POST.get("location") or "").strip()

    if not email:
        messages.error(request, "Please enter a valid email.")
        return redirect("job_list")

    JobAlert.objects.create(email=email, q=q, location=location)
    messages.success(request, "Job alert created. You can unsubscribe from any alert email.")

    params = ""
    if q or location:
        params = f"?q={q}&location={location}"
    return redirect(f"{reverse('job_list')}{params}")


# ----------------- Auth -----------------
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


@login_required
def post_login_redirect(request):
    if hasattr(request.user, "employer"):
        emp = request.user.employer
        if not emp.is_approved:
            messages.warning(request, "Your employer account is pending approval.")
            return redirect("home")
        return redirect("employer_dashboard")

    if hasattr(request.user, "jobseeker"):
        js = request.user.jobseeker
        if not js.is_approved:
            messages.warning(request, "Your job seeker account is pending approval.")
            return redirect("home")
        return redirect("jobseeker_dashboard")

    return redirect("home")


# ----------------- Employer dashboard & actions -----------------
@login_required
def employer_dashboard(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    today = timezone.now().date()

    # Active credits summary (non-expired purchases)
    active_purchases = emp.purchases.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=today))
    credits_total_active = active_purchases.aggregate(t=Sum("credits_total"))["t"] or 0
    credits_used_active = active_purchases.aggregate(u=Sum("credits_used"))["u"] or 0
    credits_active_left = max(int(credits_total_active) - int(credits_used_active), 0)

    # Jobs + metrics used by tabs
    jobs_qs = list(emp.jobs.all().order_by("-posting_date", "-id")[:50])

    for j in jobs_qs:
        apps_count = 0
        for rel in ("applications", "application_set", "jobapplication_set"):
            if hasattr(j, rel):
                try:
                    apps_count = getattr(j, rel).all().count()
                    break
                except Exception:
                    pass
        views_count = 0
        for field in ("views_count", "view_count", "views"):
            if hasattr(j, field):
                try:
                    v = getattr(j, field)
                    views_count = v() if callable(v) else (int(v) if v is not None else 0)
                    break
                except Exception:
                    pass
        j.metrics_applications = apps_count
        j.metrics_views = views_count

    purchases = list(emp.purchases.all().order_by("-purchased_at"))
    invoices = list(emp.invoices.all().order_by("-created_at"))

    # Pre-format display fields for templates (no leading underscores)
    for inv in invoices:
        cents = int(getattr(inv, "amount_cents", 0) or 0)
        inv.amount_display = f"${cents/100:.2f}"

    for p in purchases:
        related_invoice = None
        try:
            related_invoice = next(
                (inv for inv in invoices if getattr(inv, "amount_cents", 0) > 0 and inv.created_at.date() >= p.purchased_at.date()),
                None
            )
        except Exception:
            related_invoice = None

        p.source_label = "Paid (Invoice)" if related_invoice else "Manual grant / Free"
        if related_invoice:
            cents = int(getattr(related_invoice, "amount_cents", 0) or 0)
            p.price_display = f"${cents/100:.2f}"
        else:
            p.price_display = ""

    return render(
        request,
        "employers/dashboard.html",
        {
            "employer": emp,
            "credits_active_left": credits_active_left,
            "jobs": jobs_qs,
            "purchases": purchases,
            "invoices": invoices,
            "today": today,
        },
    )


@login_required
def post_job(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    now = timezone.now()
    purchase = (
        emp.purchases.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=now.date()),
            credits_used__lt=F("credits_total"),
        )
        .order_by("purchased_at")
        .first()
    )
    if not purchase:
        messages.error(request, "You don’t have any credits available. Please purchase a posting package.")
        return redirect("employer_dashboard")

    duration_days = int(purchase.package.duration_days or 30)
    min_expiry = now.date()
    max_expiry = (now + timedelta(days=duration_days)).date()

    if request.method == "POST":
        form = JobForm(request.POST, request.FILES, min_expiry=min_expiry, max_expiry=max_expiry)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = emp
            job.featured = False

            if job.expiry_date is None:
                job.expiry_date = max_expiry
            if job.expiry_date < min_expiry:
                job.expiry_date = min_expiry
            if job.expiry_date > max_expiry:
                job.expiry_date = max_expiry

            job.is_active = True
            job.save()

            purchase.credits_used = (purchase.credits_used or 0) + 1
            purchase.save(update_fields=["credits_used"])

            messages.success(request, "Job posted successfully.")
            return redirect("employer_dashboard")
    else:
        initial = {"expiry_date": max_expiry}
        form = JobForm(initial=initial, min_expiry=min_expiry, max_expiry=max_expiry)

    return render(
        request,
        "employers/post_job.html",
        {"form": form, "duration_days": duration_days, "min_expiry": min_expiry, "max_expiry": max_expiry},
    )


@login_required
def edit_job(request, pk: int):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    job = get_object_or_404(Job, pk=pk, employer=emp)

    now = timezone.now()
    purchase = (
        emp.purchases.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now.date()))
        .order_by("purchased_at")
        .first()
    )
    duration_days = int(purchase.package.duration_days) if purchase else 30

    basis = job.posting_date or now.date()
    if hasattr(basis, "date"):
        basis = basis.date()

    min_expiry = now.date()
    max_expiry = basis + timedelta(days=duration_days)

    if request.method == "POST":
        form = JobForm(request.POST, request.FILES, instance=job, min_expiry=min_expiry, max_expiry=max_expiry)
        if form.is_valid():
            job = form.save(commit=False)

            if job.expiry_date is None:
                job.expiry_date = max_expiry
            if job.expiry_date < min_expiry:
                job.expiry_date = min_expiry
            if job.expiry_date > max_expiry:
                job.expiry_date = max_expiry

            job.save()
            messages.success(request, "Job updated successfully.")
            return redirect("employer_dashboard")
    else:
        initial = {"expiry_date": job.expiry_date or max_expiry}
        form = JobForm(instance=job, initial=initial, min_expiry=min_expiry, max_expiry=max_expiry)

    return render(
        request,
        "employers/edit_job.html",
        {"form": form, "job": job, "duration_days": duration_days, "min_expiry": min_expiry, "max_expiry": max_expiry},
    )


@login_required
def applications_list(request, job_id: int):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")
    job = get_object_or_404(Job, id=job_id, employer=emp)
    apps_rel = None
    for rel in ("applications", "application_set", "jobapplication_set"):
        if hasattr(job, rel):
            apps_rel = getattr(job, rel)
            break
    applications = apps_rel.all() if apps_rel is not None else []
    return render(request, "employers/applications_list.html", {"job": job, "applications": applications})


@login_required
def employer_profile_edit(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    class EmployerEditForm(forms.ModelForm):
        class Meta:
            model = Employer
            fields = ["company_name", "name", "email", "phone", "website", "location", "logo", "description"]

    if request.method == "POST":
        form = EmployerEditForm(request.POST, request.FILES, instance=emp)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("employer_dashboard")
    else:
        form = EmployerEditForm(instance=emp)
    return render(request, "employers/profile_edit.html", {"form": form})


@login_required
def purchased_products(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")
    purchases = emp.purchases.all().order_by("-purchased_at")
    return render(request, "employers/purchased_products.html", {"purchases": purchases})


# ----------------- Employer invoices -----------------
@login_required
def invoices_list(request):
    if not hasattr(request.user, "employer"):
        return render(request, "403.html", status=403)
    emp = request.user.employer
    invoices = emp.invoices.all().order_by("-created_at")
    return render(request, "employers/invoices_list.html", {"invoices": invoices})


@login_required
def invoice_detail(request, pk: int):
    if not hasattr(request.user, "employer"):
        return render(request, "403.html", status=403)
    emp = request.user.employer
    invoice = get_object_or_404(Invoice, pk=pk, employer=emp)
    return render(request, "employers/invoice_detail.html", {"invoice": invoice})


# ----------------- Jobseeker dashboard & resume upload -----------------
@login_required
def jobseeker_dashboard(request):
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")

    recent_jobs = Job.objects.filter(is_active=True).order_by("-posting_date")[:20]

    resumes = list(js.resumes.all().order_by("-uploaded_at"))
    for r in resumes:
        if not hasattr(r, "created_at"):
            r.created_at = getattr(r, "uploaded_at", None)

    applications = list(
        Application.objects.filter(jobseeker=js).select_related("job", "job__employer").order_by("-created_at")
    )
    for a in applications:
        if not hasattr(a, "get_status_display"):
            def _status_display(_self=a):
                return "Submitted"
            a.get_status_display = _status_display

    saved_jobs = list(
        SavedJob.objects.filter(jobseeker=js).select_related("job", "job__employer").order_by("-created_at")
    )
    for s in saved_jobs:
        if not hasattr(s, "saved_at"):
            s.saved_at = getattr(s, "created_at", None)
        if not hasattr(s, "employer"):
            s.employer = getattr(getattr(s, "job", None), "employer", None)
        if not hasattr(s, "title"):
            s.title = getattr(getattr(s, "job", None), "title", "")
        if not hasattr(s, "location"):
            s.location = getattr(getattr(s, "job", None), "location", "")
        if not hasattr(s, "job_id"):
            s.job_id = getattr(getattr(s, "job", None), "id", None)

    return render(
        request,
        "board/jobseeker_dashboard.html",
        {
            "jobseeker": js,
            "recent_jobs": recent_jobs,
            "resumes": resumes,
            "applications": applications,
            "saved_jobs": saved_jobs,
        },
    )


@login_required
def upload_resume(request):
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")

    class UploadResumeForm(forms.ModelForm):
        class Meta:
            model = Resume
            fields = ["title", "file"]
            widgets = {
                "title": forms.TextInput(attrs={"class": "form-control"}),
                "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            }

    if request.method == "POST":
        form = UploadResumeForm(request.POST, request.FILES)
        if form.is_valid():
            r = form.save(commit=False)
            r.jobseeker = js
            r.save()
            messages.success(request, "Resume uploaded.")
            return redirect("jobseeker_dashboard")
    else:
        form = UploadResumeForm()

    return render(request, "board/upload_resume.html", {"form": form})
