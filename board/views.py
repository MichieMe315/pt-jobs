# board/views.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from .forms import (
    EmployerSignUpForm,
    JobSeekerSignUpForm,
    JobForm,
    JobApplicationForm,
    JobAlertForm,
    ResumeUploadForm,
    LoginForm,
    validate_no_links_or_emails,
)
from .models import (
    Employer,
    JobSeeker,
    Job,
    Application,
    Resume,
    PostingPackage,
    PurchasedPackage,
    Invoice,
    DiscountCode,
    SiteSettings,
    EmailTemplate,
    PaymentGatewayConfig,
    JobAlert,
    CareerFitLead,
)

# ============================================================
# Site / Approval / Expiry helpers
# ============================================================

def _sitesettings() -> Optional[SiteSettings]:
    return SiteSettings.objects.first()


def _enforce_approval_or_logout(request: HttpRequest) -> bool:
    """
    Contract:
      - Unapproved users cannot be logged in
      - If approval is revoked while logged in (e.g. employer profile edit),
        boot them immediately.
    Returns True if session remains valid, False if we logged them out.
    """
    user = request.user
    if not user.is_authenticated:
        return True
    if user.is_staff or user.is_superuser:
        return True

    if hasattr(user, "employer"):
        emp = user.employer
        if getattr(emp, "login_active", True) is False:
            logout(request)
            messages.error(request, "Your employer account is disabled.")
            return False
        if getattr(emp, "is_approved", False) is False:
            logout(request)
            messages.error(request, "Your employer account is pending approval.")
            return False

    if hasattr(user, "jobseeker"):
        js = user.jobseeker
        if getattr(js, "login_active", True) is False:
            logout(request)
            messages.error(request, "Your job seeker account is disabled.")
            return False
        if getattr(js, "is_approved", False) is False:
            logout(request)
            messages.error(request, "Your job seeker account is pending approval.")
            return False

    return True


def _posting_duration_days() -> int:
    ss = _sitesettings()
    if ss and getattr(ss, "posting_duration_days", None):
        try:
            return int(ss.posting_duration_days)
        except Exception:
            pass
    return 30


def _max_expiry_date(posting_date) -> object:
    # Contract: max expiry = posting_date + posting_duration_days (server-side enforced)
    days = max(1, int(_posting_duration_days() or 1))
    # inclusive end-date behavior: last day = posting_date + (days - 1)
    return posting_date + timedelta(days=days - 1)


def _clamp_expiry(posting_date, expiry_date):
    max_exp = _max_expiry_date(posting_date)
    if not expiry_date:
        return max_exp
    if expiry_date > max_exp:
        return max_exp
    return expiry_date


def _deactivate_expired_jobs() -> int:
    """
    HARD REQUIREMENT: expired jobs must stop being active.
    Sends employer expiration email ONCE per job (expiry_email_sent flag).
    """
    today = timezone.localdate()

    qs = Job.objects.filter(
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=today,
    ).select_related("employer")

    # Send email only once per job
    for job in qs.filter(expiry_email_sent=False):
        employer_email = (getattr(job.employer, "email", "") or "").strip()
        if employer_email:
            send_templated_email(
                "job_expiration_notice",
                [employer_email],
                {"job_title": getattr(job, "title", "")},
            )
        job.expiry_email_sent = True
        job.save(update_fields=["expiry_email_sent"])

    return qs.update(is_active=False)


def _active_jobs_qs():
    """
    Even if some stale rows still have is_active=True,
    NEVER show expired jobs publicly.
    """
    today = timezone.localdate()
    return Job.objects.filter(is_active=True).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))


# ============================================================
# Email helpers (Admin-controlled EmailTemplate)
# ============================================================

def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@physiotherapyjobscanada.ca"


def _admin_emails() -> list[str]:
    """
    CONTRACT: admin notification recipient comes from SiteSettings (admin-managed).
    Field: SiteSettings.contact_email  (Admin label: "Contact email")
    """
    ss = _sitesettings()
    if not ss:
        return []

    email = (getattr(ss, "contact_email", "") or "").strip()
    return [email] if email else []


def _render_tokens(text: str, context: dict) -> str:
    out = text or ""
    for k, v in (context or {}).items():
        out = out.replace("{{ " + str(k) + " }}", str(v))
        out = out.replace("{{" + str(k) + "}}", str(v))
    return out


def send_templated_email(key: str, to_emails: list[str], context: dict) -> bool:
    """
    Contract-safe:
      - Only sends if EmailTemplate(key) exists AND is_enabled=True AND has subject+html
      - No silent fallback body content
    """
    to_emails = [e.strip() for e in (to_emails or []) if (e or "").strip()]
    if not to_emails:
        return False

    tmpl = EmailTemplate.objects.filter(key=key, is_enabled=True).first()
    if not tmpl:
        return False

    subject_raw = (tmpl.subject or "").strip()
    html_raw = (tmpl.html or "").strip()
    if not subject_raw or not html_raw:
        return False

    subject = _render_tokens(subject_raw, context).strip()
    html_body = _render_tokens(html_raw, context).strip()
    if not subject or not html_body:
        return False

    try:
        from django.core.mail import EmailMultiAlternatives
        from .notification_mail import email_frame
        from django.utils.html import escape, strip_tags
        review_url = context.get('review_url')
        if review_url:
            html_body += f'<p><a href="{escape(review_url)}" style="display:inline-block;background:#b72d38;color:#fff;padding:12px 18px;text-decoration:none">Review in admin</a></p>'
        if context.get('next_step'):
            html_body += '<hr><p>'+str(escape(context['next_step']))+'</p>'
            if context.get('next_step_url'):
                html_body += '<p><a href="'+str(escape(context['next_step_url']))+'">Continue on PTJC</a></p>'
        text_body = strip_tags(html_body)
        subject = ' '.join(subject.splitlines())
        if not subject.startswith('[PTJC]'):
            subject = '[PTJC] ' + subject
        msg = EmailMultiAlternatives(subject, text_body, _default_from_email(), to_emails)
        if key.startswith('admin_') and context.get('email'):
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(context['email'])
                msg.reply_to = [context['email']]
            except ValidationError:
                pass
        msg.attach_alternative(email_frame(subject, html_body), "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception:
        return False



# ============================================================
# Payment gateway helpers (Stripe / PayPal)
# ============================================================

def _gateway_config() -> Optional[PaymentGatewayConfig]:
    try:
        return PaymentGatewayConfig.get_active_gateway()
    except Exception:
        return PaymentGatewayConfig.objects.filter(is_active=True).order_by("-updated_at", "-id").first()


def _stripe_enabled(cfg: Optional[PaymentGatewayConfig]) -> bool:
    if not cfg:
        return False
    pub = (getattr(cfg, "stripe_public_key", "") or getattr(cfg, "stripe_publishable_key", "") or "").strip()
    sec = (getattr(cfg, "stripe_secret_key", "") or "").strip()
    return bool(getattr(cfg, "use_stripe", False) and pub and sec)


def _paypal_enabled(cfg: Optional[PaymentGatewayConfig]) -> bool:
    if not cfg:
        return False
    # Do not offer a payment method without server-side order capture.
    return False


def _gateway_context() -> dict:
    cfg = _gateway_config()
    return {
        # support both key names (your model has both)
        "stripe_publishable_key": (getattr(cfg, "stripe_public_key", "") or getattr(cfg, "stripe_publishable_key", "") or "").strip() if cfg else "",
        "stripe_public_key": (getattr(cfg, "stripe_public_key", "") or getattr(cfg, "stripe_publishable_key", "") or "").strip() if cfg else "",
        "stripe_secret_key": getattr(cfg, "stripe_secret_key", "") if cfg else "",
        "paypal_client_id": getattr(cfg, "paypal_client_id", "") if cfg else "",
        "paypal_mode": getattr(cfg, "paypal_mode", "sandbox") if cfg else "sandbox",
        "currency": getattr(cfg, "currency", "CAD") if cfg else "CAD",
        "use_stripe": _stripe_enabled(cfg),
        "use_paypal": _paypal_enabled(cfg),
    }


def _apply_discount(package: PostingPackage, code_raw: str) -> tuple[Optional[DiscountCode], Decimal, Optional[str]]:
    # Keep stable behavior using Decimal price
    base = Decimal(str(package.price))
    code = (code_raw or "").strip()
    if not code:
        return None, base, None

    today = timezone.now().date()
    dc = DiscountCode.objects.filter(code__iexact=code, is_active=True).first()
    if not dc:
        return None, base, "Invalid discount code."

    if getattr(dc, "start_date", None) and today < dc.start_date:
        return None, base, "This discount code is not active yet."
    if getattr(dc, "end_date", None) and today > dc.end_date:
        return None, base, "This discount code has expired."

    try:
        if dc.kind == "percent":
            pct = Decimal(str(dc.value))
            final = base * (Decimal("1.0") - (pct / Decimal("100.0")))
        else:
            # dc.value is int cents in your model; convert to dollars
            final = base - (Decimal(int(dc.value or 0)) / Decimal("100"))
    except Exception:
        return None, base, "Invalid discount configuration."

    if final < 0:
        final = Decimal("0.00")
    return dc, final.quantize(Decimal("0.01")), None


# ============================================================
# Credits / package helpers (CONTRACT-SAFE)
# ============================================================

def _available_packages_qs(employer: Employer):
    """
    Contract: credit counter shows UNEXPIRED credits only.
    expires_at can be NULL -> treat NULL as not expired.
    """
    now = timezone.now()
    return (
        PurchasedPackage.objects.filter(employer=employer, credits_remaining__gt=0)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    )


def _available_credits(employer: Employer) -> int:
    if not PurchasedPackage.objects.filter(employer=employer).exists():
        return max(0, int(employer.credits or 0))
    total = _available_packages_qs(employer).aggregate(total=Sum("credits_remaining"))["total"]
    return int(total or 0)


def _sync_employer_credits(employer: Employer) -> None:
    # Legacy-only balances remain authoritative until package records exist.
    with transaction.atomic():
        locked = Employer.objects.select_for_update().get(pk=employer.pk)
        total = _available_credits(locked)
        Employer.objects.filter(pk=locked.pk).update(credits=total)
        employer.credits = total


@transaction.atomic
def _consume_employer_credit(employer: Employer) -> bool:
    locked = Employer.objects.select_for_update().get(pk=employer.pk)
    pkg = _available_packages_qs(locked).select_for_update().order_by("expires_at", "id").first()
    if pkg:
        consumed = PurchasedPackage.objects.filter(pk=pkg.pk, credits_remaining__gt=0).update(
            credits_remaining=F("credits_remaining") - 1
        )
        _sync_employer_credits(locked)
        employer.credits = locked.credits
        return bool(consumed)
    # Never resurrect expired or exhausted package balances through the cache.
    if not PurchasedPackage.objects.filter(employer=locked).exists():
        consumed = Employer.objects.filter(pk=locked.pk, credits__gt=0).update(credits=F("credits") - 1)
        locked.refresh_from_db(fields=["credits"])
        employer.credits = locked.credits
        return bool(consumed)
    _sync_employer_credits(locked)
    employer.credits = locked.credits
    return False


# ============================================================
# Public pages
# ============================================================

def home(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    jobs = (
        _active_jobs_qs()
        .select_related("employer")
        .order_by("-posting_date", "-id")[:6]
    )
    featured_jobs = (
        _active_jobs_qs()
        .filter(is_featured=True)
        .select_related("employer")
        .order_by("-posting_date", "-id")[:6]
    )
    job_alert_form = JobAlertForm()

    return render(
        request,
        "board/home.html",
        {
            "sitesettings": ss,
            "jobs": jobs,
            "featured_jobs": featured_jobs,
            "job_alert_form": job_alert_form,
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "board/about.html", {"sitesettings": _sitesettings()})


from django.core.mail import send_mail
from django.conf import settings

def contact(request):
    context = {}

    if request.method == "POST":
        # Block bots (honeypot)
        if request.POST.get("website"):
            return redirect("contact")

        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        message = (request.POST.get("message") or "").strip()

        # Block common SEO spam contact-form pitches
        spam_phrases = [
            "technical seo",
            "indexing and optimization",
            "rank better",
            "main keywords",
            "relevant traffic",
            "happy to share more",
            "seo areas",
            "seo expert",
            "google ranking",
            "increase your traffic",
            "digital marketing",
            "backlinks",
        ]

        message_lower = message.lower()
        if any(phrase in message_lower for phrase in spam_phrases):
            return redirect("contact")

        context.update({
            "form_name": name,
            "form_email": email,
            "form_message": message,
        })

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
            email_valid = not any(c in email for c in '\r\n')
        except ValidationError:
            email_valid = False
        if name and email and message and email_valid and len(name) <= 150 and len(message) <= 12000 and not any(c in name for c in '\r\n'):
            try:
                ss = _sitesettings()
                to_email = getattr(ss, "contact_email", None) or settings.DEFAULT_FROM_EMAIL

                from django.core.mail import EmailMultiAlternatives
                from django.utils.html import escape
                from .notification_mail import email_frame
                text = f"Contact message from {name} <{email}>\n\n{message}\n\nReply to this email to answer {name}."
                mail = EmailMultiAlternatives(
                    subject=f"[PTJC] Contact: {name}", body=text,
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[to_email], reply_to=[email],
                )
                mail.attach_alternative(email_frame('Contact message',
                    f'<p><strong>{escape(name)}</strong><br>{escape(email)}</p><div style="white-space:pre-wrap">{escape(message)}</div><p>Reply to this email to answer the sender.</p>'), 'text/html')
                mail.send(fail_silently=False)

                context["submitted"] = True

            except Exception:
                context["error"] = "There was an error sending your message."
        else:
            context["error"] = "Enter your name, a valid email address and a message (maximum 12,000 characters)."

    return render(request, "board/contact.html", context)



def terms(request: HttpRequest) -> HttpResponse:
    return render(request, "board/terms.html", {"sitesettings": _sitesettings()})


# ============================================================
# Auth
# ============================================================

def logout_view(request: HttpRequest) -> HttpResponse:
    # Logout must never crash. Do NOT touch employer/jobseeker objects here.
    try:
        logout(request)
    except Exception:
        pass
    return redirect("home")


def login_view(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()

            # Contract: unapproved users cannot log in
            if hasattr(user, "employer") and not user.employer.is_approved:
                messages.error(
                    request,
                    "Your employer account is pending approval. You will receive an email when admin approves your account.",
                )
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            if hasattr(user, "jobseeker") and not user.jobseeker.is_approved:
                messages.error(
                    request,
                    "Your job seeker account is pending approval. You will receive an email when admin approves your account.",
                )
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            login(request, user)

            # safety: if approval revoked between credential check and session
            if hasattr(request.user, "employer") and not getattr(request.user.employer, "is_approved", True):
                logout(request)
                messages.error(request, "Your employer account is pending approval.")
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            if hasattr(request.user, "jobseeker") and not getattr(request.user.jobseeker, "is_approved", True):
                logout(request)
                messages.error(request, "Your job seeker account is pending approval.")
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            nxt = request.GET.get("next")
            if nxt and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(nxt)

            if hasattr(user, "employer"):
                return redirect("employer_dashboard")
            if hasattr(user, "jobseeker"):
                return redirect("jobseeker_dashboard")
            return redirect("home")

        messages.error(request, "Please correct the errors below.")

    return render(request, "board/login.html", {"sitesettings": ss, "form": form})


# ============================================================
# Job Alerts
# ============================================================

def job_alert_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = JobAlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        alert, _ = JobAlert.objects.get_or_create(
            email=form.cleaned_data["email"],
            q=form.cleaned_data["q"],
            location=form.cleaned_data["location"],
            defaults={"active": True},
        )
        if not alert.active:
            alert.active = True
            alert.save(update_fields=["active"])
        messages.success(request, "Thanks! You’re signed up for job alerts.")
        return redirect("home")
    return render(request, "board/job_alert_signup.html", {"sitesettings": ss, "form": form})


# ============================================================
# Employer signup + list + detail
# ============================================================

def employer_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = EmployerSignUpForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            # Prevent 500 on duplicate email (show error only on submit)
            form.add_error(
                "email",
                "An account with this email already exists. Please log in or use a different email.",
            )
            return render(request, "board/employer_signup.html", {"sitesettings": ss, "form": form})

        # Admin notification + optional welcome (admin-controlled templates)
        admin_emails = _admin_emails()
        send_templated_email("admin_new_employer", admin_emails, {"email": user.email,
            "review_url": request.build_absolute_uri(reverse('admin:board_employer_change', args=[user.employer.pk]))})
        send_templated_email(
            "employer_welcome",
            [user.email],
            {"email": user.email, "login_url": reverse("login")},
        )

        messages.success(
            request,
            "Your account has been created. You will be notified via email when admin approves your account.",
        )
        return redirect("login")

    return render(request, "board/employer_signup.html", {"sitesettings": ss, "form": form})



def employer_list(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    employers = (
        Employer.objects.annotate(active_jobs=Count("jobs", filter=Q(jobs__is_active=True)))
        .filter(active_jobs__gt=0)
        .order_by("company_name", "id")
    )
    return render(request, "board/employer_list.html", {"sitesettings": ss, "employers": employers})


def employer_detail(request: HttpRequest, employer_id: int) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    employer = get_object_or_404(Employer, id=employer_id)
    jobs = _active_jobs_qs().filter(employer=employer).order_by("-posting_date", "-id")

    return render(
        request,
        "board/employer_detail.html",
        {"sitesettings": ss, "employer": employer, "jobs": jobs},
    )


# ============================================================
# Job Seeker signup
# ============================================================

def jobseeker_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = JobSeekerSignUpForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            # Prevent 500 on duplicate email (show error only on submit)
            form.add_error(
                "email",
                "An account with this email already exists. Please log in or use a different email.",
            )
            return render(request, "board/jobseeker_signup.html", {"sitesettings": ss, "form": form})

        admin_emails = _admin_emails()
        send_templated_email("admin_new_jobseeker", admin_emails, {"email": user.email,
            "review_url": request.build_absolute_uri(reverse('admin:board_jobseeker_change', args=[user.jobseeker.pk]))})
        send_templated_email(
            "jobseeker_welcome",
            [user.email],
            {"email": user.email, "login_url": reverse("login")},
        )

        messages.success(request, "Account created. Your job seeker account requires admin approval before login.")
        return redirect("login")

    return render(request, "board/jobseeker_signup.html", {"sitesettings": ss, "form": form})



# ============================================================
# Jobs
# ============================================================

def job_list(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    q = (request.GET.get("q") or "").strip()
    loc = (request.GET.get("location") or "").strip()
    job_type = (request.GET.get("job_type") or "").strip()

    qs = _active_jobs_qs().select_related("employer")

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(employer__company_name__icontains=q)
        )

    if loc:
        raw_loc = loc.strip()

        # Normalize Mapbox/full-place input like:
        # "Toronto, Ontario, Canada" -> "Toronto"
        first_part = raw_loc.split(",")[0].strip()

        # Safe alias expansion for Toronto-area boroughs / common subregions
        alias_map = {
            "north york": ["north york", "toronto"],
            "scarborough": ["scarborough", "toronto"],
            "etobicoke": ["etobicoke", "toronto"],
            "east york": ["east york", "toronto"],
            "york": ["york", "toronto"],
            "downtown toronto": ["downtown toronto", "toronto"],
            "midtown toronto": ["midtown toronto", "toronto"],
            "toronto": ["toronto", "north york", "scarborough", "etobicoke", "east york", "york"],
        }

        normalized_key = first_part.lower()

        search_terms = []
        for candidate in [raw_loc, first_part]:
            candidate = candidate.strip()
            if candidate and candidate.lower() not in [t.lower() for t in search_terms]:
                search_terms.append(candidate)

        if normalized_key in alias_map:
            for term in alias_map[normalized_key]:
                if term.lower() not in [t.lower() for t in search_terms]:
                    search_terms.append(term)

        location_query = Q()
        for term in search_terms:
            location_query |= Q(location__icontains=term)

        qs = qs.filter(location_query)

    if job_type:
        qs = qs.filter(job_type=job_type)

    jobs = qs.order_by("-posting_date", "-id")
    return render(
        request,
        "board/job_list.html",
        {
            "sitesettings": ss,
            "jobs": jobs,
            "q": q,
            "location": loc,
            "job_type": job_type,
        },
    )


def job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    # allow viewing inactive detail page if template expects it; but keep public list filtered
    job = get_object_or_404(Job.objects.select_related("employer"), id=job_id)
    if not job.is_active:
        owner = request.user.is_authenticated and job.employer.user_id == request.user.pk
        expired = bool(job.expiry_date and job.expiry_date < timezone.localdate())
        previously_published = expired and job.expiry_email_sent
        if not (request.user.is_staff or owner or previously_published):
            from django.http import Http404
            raise Http404
    job_alert_form = JobAlertForm()
    return render(
        request,
        "board/job_detail.html",
        {"sitesettings": ss, "job": job, "job_alert_form": job_alert_form},
    )


@login_required
@transaction.atomic
def job_create(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = Employer.objects.select_for_update().get(pk=request.user.employer.pk)

    posting_date = timezone.localdate()
    max_expiry = _max_expiry_date(posting_date)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    if active_package:
        from .publication import duration_for
        max_expiry=posting_date+timedelta(days=duration_for(active_package)-1)
    form = JobForm(request.POST or None, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.source = "employer"
        job.employer = employer
        job.posting_date = posting_date

        # HARD expiry clamp server-side
        job.expiry_date = _clamp_expiry(posting_date, getattr(job, "expiry_date", None))

        action = (request.POST.get("action") or "").strip().lower()
        if action not in ('publish','draft'):
            messages.error(request,'Choose Publish or Save Draft.')
            return redirect(request.path)
        publish = action == "publish"
        job.is_active = bool(publish)

        if publish:
            ok = _consume_employer_credit(employer)
            if not ok:
                job.is_active = False
                job.save()
                request.session["pending_create_job_id"] = job.id
                from .publication import request_publication
                request_publication(job,reuse=True)
                messages.error(
                    request,
                    "No credits available. Your job was saved as a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        job.save()
        from .publication import finish_direct,cancel_requests
        if publish:finish_direct(job,active_package)
        else:cancel_requests(job)
        _sync_employer_credits(employer)

        if publish:
            from .publication import notify_publication
            transaction.on_commit(lambda pk=job.pk:notify_publication(pk))
            for key in ('pending_create_job_id','pending_publish_job_id','pending_duplicate_job_id'):
                if request.session.get(key)==job.pk:request.session.pop(key,None)

        messages.success(request, "Job created.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
            "form": form,
            "mode": "create",
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
        },
    )


@login_required
@transaction.atomic
def job_edit(request: HttpRequest, job_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = Employer.objects.select_for_update().get(pk=request.user.employer.pk)
    job = get_object_or_404(Job.objects.select_for_update(), id=job_id, employer=employer)

    was_inactive = not job.is_active
    existing_posting_date = job.posting_date or timezone.localdate()
    existing_expiry_date = job.expiry_date
    form_posting_date = timezone.localdate() if was_inactive else existing_posting_date
    max_expiry = _max_expiry_date(form_posting_date)
    if not was_inactive and existing_expiry_date:max_expiry=existing_expiry_date

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    from .publication import duration_for
    if active_package:max_expiry=timezone.localdate()+timedelta(days=duration_for(active_package)-1) if was_inactive else max_expiry
    form = JobForm(request.POST or None, instance=job, max_expiry_date=max_expiry,initial={'expiry_date':max_expiry} if was_inactive else None)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        if not updated.source:
            updated.source = "employer"

        action = (request.POST.get("action") or "").strip().lower()
        if action not in ('publish','draft'):
            messages.error(request,'Choose Publish or Save Draft.')
            return redirect(request.path)
        publish = action == "publish"

        # A previously inactive job being published (including after a credit
        # purchase) starts a fresh posting window. Draft edits and edits to an
        # already-active job keep their existing posting window.
        posting_date = timezone.localdate() if (publish and was_inactive) else existing_posting_date
        updated.posting_date = posting_date
        if publish and not was_inactive:
            updated.expiry_date=min(updated.expiry_date or max_expiry,max_expiry)
        else:
            updated.expiry_date = _clamp_expiry(posting_date, getattr(updated, "expiry_date", None))
        updated.is_active = bool(publish)
        if publish and was_inactive:
            updated.expiry_email_sent = False

        if publish and was_inactive:
            ok = _consume_employer_credit(employer)
            if not ok:
                updated.is_active = False
                updated.save()
                request.session["pending_publish_job_id"] = updated.id
                from .publication import request_publication
                request_publication(updated,reuse=True)
                messages.error(
                    request,
                    "No credits available. This job remains a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        updated.save()
        from .publication import finish_direct,cancel_requests
        if publish and was_inactive:finish_direct(updated,active_package)
        elif not publish:cancel_requests(updated)
        _sync_employer_credits(employer)

        if publish and was_inactive:
            for pending_key in (
                "pending_create_job_id",
                "pending_publish_job_id",
                "pending_duplicate_job_id",
            ):
                if request.session.get(pending_key) == updated.id:
                    request.session.pop(pending_key, None)

        # OPTIONAL: notify admin if a draft becomes published via edit
        if publish and was_inactive:
            from .publication import notify_publication
            transaction.on_commit(lambda pk=updated.pk:notify_publication(pk))

        messages.success(request, "Job updated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
            "form": form,
            "mode": "edit",
            "job": job,
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
        },
    )


@login_required
@transaction.atomic
def job_duplicate(request: HttpRequest, job_id: int) -> HttpResponse:
    """
    Employer duplicate:
      - opens standard job form
      - does NOT consume credit until publish
      - expiry is recalculated + clamped
    """
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = Employer.objects.select_for_update().get(pk=request.user.employer.pk)
    original = get_object_or_404(Job.objects.select_for_update(), id=job_id, employer=employer)

    posting_date = timezone.localdate()
    max_expiry = _max_expiry_date(posting_date)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    if active_package:
        from .publication import duration_for
        max_expiry=posting_date+timedelta(days=duration_for(active_package)-1)

    initial = {
        "title": original.title,
        "description": original.description,
        "job_type": original.job_type,
        "compensation_type": original.compensation_type,
        "compensation_min": original.compensation_min,
        "compensation_max": original.compensation_max,
        "location": original.location,
        "apply_via": original.apply_via,
        "apply_email": original.apply_email,
        "apply_url": original.apply_url,
        "relocation_assistance": "yes" if bool(original.relocation_assistance) else "no",
        "expiry_date": max_expiry,
    }

    form = JobForm(request.POST or None, initial=initial, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.source = "employer"
        job.employer = employer
        job.posting_date = posting_date

        # HARD expiry clamp server-side
        job.expiry_date = _clamp_expiry(posting_date, getattr(job, "expiry_date", None))

        action = (request.POST.get("action") or "").strip().lower()
        if action not in ('publish','draft'):
            messages.error(request,'Choose Publish or Save Draft.')
            return redirect(request.path)
        publish = action == "publish"
        job.is_active = bool(publish)

        if publish:
            ok = _consume_employer_credit(employer)
            if not ok:
                job.is_active = False
                job.save()
                request.session["pending_duplicate_job_id"] = job.id
                from .publication import request_publication
                request_publication(job,reuse=True)
                messages.error(
                    request,
                    "No credits available. Your duplicated job was saved as a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        job.save()
        from .publication import finish_direct,cancel_requests
        if publish:finish_direct(job,active_package)
        else:cancel_requests(job)
        _sync_employer_credits(employer)

        if publish:
            from .publication import notify_publication
            transaction.on_commit(lambda pk=job.pk:notify_publication(pk))
            for key in ('pending_create_job_id','pending_publish_job_id','pending_duplicate_job_id'):
                if request.session.get(key)==job.pk:request.session.pop(key,None)


        messages.success(request, "Job duplicated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
            "form": form,
            "mode": "duplicate",
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
            "original": original,
        },
    )


def job_apply(request: HttpRequest, job_id: int) -> HttpResponse:
    _deactivate_expired_jobs()

    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('apply_to_job', args=[job_id])}")

    if not hasattr(request.user, "jobseeker"):
        return redirect("home")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    js = request.user.jobseeker

    job = get_object_or_404(_active_jobs_qs().select_related("employer"), id=job_id)
    resumes = Resume.objects.filter(jobseeker=js).order_by("-created_at", "-id")

    form = JobApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resume_id = (request.POST.get("resume_id") or "").strip()
        try:
            resume_obj = resumes.filter(id=int(resume_id)).first() if resume_id else None
        except (ValueError, TypeError, OverflowError):
            resume_obj = None

        if resume_obj is None:
            messages.error(request, "Please select a resume to attach.")
        else:
            # prevent duplicates
            if Application.objects.filter(job=job, jobseeker=js).exists():
                messages.info(request, "You’ve already applied to this job.")
                return redirect("job_detail", job_id=job.id)

            app = form.save(commit=False)
            app.job = job
            app.jobseeker = js
            app.resume_selected = resume_obj
            app.save()

            # Employer notification email (admin-controlled)
            employer_email = (job.apply_email or job.employer.email or "").strip()
            send_templated_email(
                "application_email_to_employer",
                [employer_email] if employer_email else [],
                {
                    "job_title": job.title,
                    "employer_name": job.employer.company_name or job.employer.email,
                    "dashboard_url": request.build_absolute_uri(reverse("employer_dashboard")),
                },
            )

            # Jobseeker confirmation (admin-controlled)
            send_templated_email(
                "jobseeker_application_confirmation",
                [(js.email or request.user.email or "").strip()],
                {"job_title": job.title, "jobs_url": request.build_absolute_uri(reverse("job_list"))},
            )

            messages.success(request, "Application submitted.")
            return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/job_apply.html",
        {
            "sitesettings": ss,
            "job": job,
            "form": form,
            "jobseeker": js,
            "resumes": resumes,
        },
    )

# ============================================================
# Career Fit Check
# ============================================================

import json

def career_fit(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()

    professions = [
        ("PT", "Physiotherapist"),
        ("OT", "Occupational Therapist"),
        ("DC", "Chiropractor"),
        ("RMT", "Registered Massage Therapist"),
        ("Osteopath", "Osteopath"),
        ("ND", "Naturopath"),
        ("SLP", "Speech-Language Pathologist"),
        ("Audiology", "Audiologist"),
    ]

    stage_choices = [
        ("student", "Student / final placement"),
        ("new_grad", "New grad (0–2 years)"),
        ("early", "Early career (3–5 years)"),
        ("established", "Established clinician (5+ years)"),
    ]

    priority_choices = [
        ("income", "Income growth"),
        ("flexibility", "Flexibility"),
        ("specialization", "Specialization"),
        ("balance", "Work sustainability"),
        ("leadership", "Leadership / ownership"),
        ("meaning", "Meaning / impact"),
    ]

    setting_choices = [
        ("private", "Private clinic"),
        ("multidisciplinary", "Multidisciplinary clinic"),
        ("hospital", "Hospital / institution"),
        ("community", "Community / home-based"),
        ("hybrid", "Hybrid / mobile / virtual"),
        ("academic", "Academic / teaching"),
    ]

    opportunity_type_choices = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contractor", "Contractor"),
        ("casual", "Casual"),
        ("locum", "Locum"),
        ("temporary", "Temporary"),
    ]

    compensation_type_choices = [
        ("hourly", "Hourly"),
        ("yearly", "Salary (yearly)"),
        ("split", "Split / percentage / per-visit"),
    ]

    schedule_choices = [
        ("daytime_only", "Daytime only"),
        ("some_evenings", "Some evenings OK"),
        ("some_weekends", "Some weekends OK"),
        ("flexible", "Flexible"),
    ]

    relocation_choices = [
        ("no", "No"),
        ("maybe", "Maybe (for the right role)"),
        ("yes", "Yes"),
    ]

    specialties = [
        "Pelvic health",
        "Neuro / concussion",
        "Sports / performance",
        "Chronic pain",
        "Pediatrics",
        "Seniors",
        "General MSK",
    ]

    return render(
        request,
        "board/career_fit.html",
        {
            "sitesettings": ss,
            "professions": professions,
            "stage_choices": stage_choices,
            "priority_choices": priority_choices,
            "setting_choices": setting_choices,
            "opportunity_type_choices": opportunity_type_choices,
            "compensation_type_choices": compensation_type_choices,
            "schedule_choices": schedule_choices,
            "relocation_choices": relocation_choices,
            "specialties": specialties,
        },
    )


@require_POST
def career_fit_results(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()

    answers = {
        "profession": (request.POST.get("profession") or "").strip(),
        "stage": (request.POST.get("stage") or "").strip(),
        "priority": (request.POST.get("priority") or "").strip(),
        "setting": (request.POST.get("setting") or "").strip(),
        "opportunity_type": (request.POST.get("opportunity_type") or "").strip(),
        "compensation_type": (request.POST.get("compensation_type") or "").strip(),
        "schedule_pref": (request.POST.get("schedule_pref") or "").strip(),
        "location": (request.POST.get("location") or "").strip(),
        "relocation_open": (request.POST.get("relocation_open") or "").strip(),
        "specialties": request.POST.getlist("specialties") or [],
        "burnout_stuck": (request.POST.get("burnout_stuck") or "").strip(),
        "burnout_undervalued": (request.POST.get("burnout_undervalued") or "").strip(),
        "burnout_exhausted": (request.POST.get("burnout_exhausted") or "").strip(),
        "new_grad_specialize": (request.POST.get("new_grad_specialize") or "").strip(),
    }

    burnout_score = sum([
        1 if answers["burnout_stuck"] == "yes" else 0,
        1 if answers["burnout_undervalued"] == "yes" else 0,
        1 if answers["burnout_exhausted"] == "yes" else 0,
    ])
    if burnout_score >= 2:
        burnout_risk = "high"
    elif burnout_score == 1:
        burnout_risk = "moderate"
    else:
        burnout_risk = "low"

    # Archetype (professional naming)
    if answers["stage"] in ("student", "new_grad"):
        archetype = "New Grad Specialization Path" if answers["new_grad_specialize"] == "yes" else "New Grad Foundations Path"
    elif answers["priority"] == "specialization":
        archetype = "Specialist Path"
    elif answers["priority"] == "income":
        archetype = "Growth Path"
    elif answers["priority"] in ("balance", "flexibility"):
        archetype = "Sustainable Practice Path"
    elif answers["priority"] == "meaning":
        archetype = "Meaning-Focused Path"
    else:
        archetype = "Sustainable Practice Path"

    roles = []
    if answers["setting"] == "hospital":
        roles.append("Hospital / institution role")
    elif answers["setting"] == "community":
        roles.append("Community / home-based role")
    elif answers["setting"] == "multidisciplinary":
        roles.append("Multidisciplinary clinic role")
    elif answers["setting"] == "private":
        roles.append("Private clinic role")
    elif answers["setting"] == "hybrid":
        roles.append("Hybrid / mobile / virtual role")
    elif answers["setting"] == "academic":
        roles.append("Academic / teaching role")

    if answers["opportunity_type"] == "contractor":
        roles.append("Contractor / split-based role")
    elif answers["opportunity_type"] == "full_time":
        roles.append("Full-time employee role")
    elif answers["opportunity_type"] == "part_time":
        roles.append("Part-time role")
    elif answers["opportunity_type"] == "locum":
        roles.append("Locum role")

    course_topics = []
    for s in answers["specialties"]:
        if s and s not in course_topics:
            course_topics.append(s)

    computed = {
        "archetype": archetype,
        "burnout_risk": burnout_risk,
        "roles_to_explore": roles[:6],
        "course_topics": course_topics[:6],
    }

    results = {"answers": answers, "computed": computed}

    return render(
        request,
        "board/career_fit_results.html",
        {
            "sitesettings": ss,
            "results": results,
            "results_json": json.dumps(results),
        },
    )


@require_POST
def career_fit_save(request: HttpRequest) -> HttpResponse:
    email = (request.POST.get("email") or "").strip()
    mode = (request.POST.get("mode") or "signup").strip().lower()
    results_json_raw = (request.POST.get("results_json") or "").strip()

    if not email:
        messages.error(request, "Please enter an email.")
        return redirect("career_fit")

    try:
        results_json = json.loads(results_json_raw) if results_json_raw else {}
    except Exception:
        results_json = {}

    lead = CareerFitLead.objects.create(email=email, results_json=results_json)

    snapshot_url = request.build_absolute_uri(reverse("career_fit_snapshot", args=[lead.token]))
    signup_url = request.build_absolute_uri(
        f"{reverse('jobseeker_signup')}?next={reverse('career_fit_claim', args=[lead.token])}"
    )
    international_url = request.build_absolute_uri(reverse("career_fit_international"))

    # Optional admin-controlled template key: career_fit_snapshot
    send_templated_email(
        "career_fit_snapshot",
        [email],
        {
            "email": email,
            "snapshot_url": snapshot_url,
            "signup_url": signup_url,
            "international_url": international_url,
        },
    )

    if mode == "international":
        return redirect("career_fit_international")

    return redirect(f"{reverse('jobseeker_signup')}?next={reverse('career_fit_claim', args=[lead.token])}")


@login_required
def career_fit_claim(request: HttpRequest, token) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        messages.error(request, "Job Seeker account required.")
        return redirect("home")

    lead = get_object_or_404(CareerFitLead, token=token)
    lead.claimed_by = request.user.jobseeker
    lead.save(update_fields=["claimed_by"])

    messages.success(request, "Career snapshot saved to your dashboard.")
    return redirect("jobseeker_dashboard")


def career_fit_snapshot(request: HttpRequest, token) -> HttpResponse:
    ss = _sitesettings()
    lead = get_object_or_404(CareerFitLead, token=token)
    return render(request, "board/career_fit_snapshot.html", {"sitesettings": ss, "lead": lead})


def career_fit_international(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    return render(request, "board/career_fit_international.html", {"sitesettings": ss})

# ============================================================
# Dashboards
# ============================================================

@login_required
def employer_dashboard(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()

    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    _sync_employer_credits(employer)

    from .models import JobPublicationRequest
    jobs = Job.objects.filter(employer=employer).order_by("-posting_date", "-id")
    applications = (
        Application.objects.filter(job__employer=employer)
        .select_related("job", "jobseeker")
        .order_by("-created_at", "-id")
    )
    invoices = Invoice.objects.filter(employer=employer).order_by("-order_date", "-id")

    packages = PurchasedPackage.objects.filter(employer=employer).order_by("-purchased_at", "-id")
    purchased_packages = packages  # template compatibility

    return render(
        request,
        "board/employer_dashboard.html",
        {
            "sitesettings": ss,
            "employer": employer,
            "jobs": jobs,
            "publication_requests": JobPublicationRequest.objects.filter(employer=employer,status__in=['waiting','ready','review']).select_related('job'),
            "saved_jobs": jobs.filter(is_active=False),
            "applications": applications,
            "invoices": invoices,
            "packages": packages,
            "purchased_packages": purchased_packages,
            "credits_available": _available_credits(employer),
            "available_credits": _available_credits(employer),
        },
    )


@login_required
def jobseeker_dashboard(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    js = request.user.jobseeker
    resumes = Resume.objects.filter(jobseeker=js).order_by("-created_at", "-id")
    applications = (
        Application.objects.filter(jobseeker=js)
        .select_related("job", "job__employer")
        .order_by("-created_at", "-id")
    )

    upload_form = ResumeUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and upload_form.is_valid():
        r = upload_form.save(commit=False)
        r.jobseeker = js
        r.save()
        messages.success(request, "Resume uploaded.")
        return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/jobseeker_dashboard.html",
        {
            "sitesettings": ss,
            "jobseeker": js,
            "resumes": resumes,
            "applications": applications,
            "upload_form": upload_form,
        },
    )


# ============================================================
# Profile edit forms + views
# ============================================================

YES_NO_CHOICES = (("yes", "Yes"), ("no", "No"))


class EmployerProfileEditForm(forms.ModelForm):
    company_description = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = Employer
        fields = ("company_name", "company_description", "phone", "website", "location", "logo")

    def clean_company_description(self):
        val = self.cleaned_data.get("company_description") or ""
        validate_no_links_or_emails(val)
        return val


class JobSeekerProfileEditForm(forms.ModelForm):
    registered_in_canada = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    open_to_relocate = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    require_sponsorship = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    seeking_immigration = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)

    class Meta:
        model = JobSeeker
        fields = (
            "first_name",
            "last_name",
            "position_desired",
            "opportunity_type",
            "current_location",
            "relocate_where",
        )

    def save(self, commit=True):
        inst = super().save(commit=False)

        def _to_bool(v: str) -> bool:
            return True if (v or "").lower() == "yes" else False

        inst.registered_in_canada = _to_bool(self.cleaned_data.get("registered_in_canada", "no"))
        inst.open_to_relocate = _to_bool(self.cleaned_data.get("open_to_relocate", "no"))
        inst.require_sponsorship = _to_bool(self.cleaned_data.get("require_sponsorship", "no"))
        inst.seeking_immigration = _to_bool(self.cleaned_data.get("seeking_immigration", "no"))

        if commit:
            inst.save()
        return inst


@login_required
def employer_profile_edit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    form = EmployerProfileEditForm(request.POST or None, request.FILES or None, instance=employer)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        # Contract: profile edit triggers re-approval
        updated.is_approved = False
        updated.save()

        # Admin notification (admin-controlled)
        from .notification_mail import profile_review_email
        profile_review_email(request, updated, _admin_emails())

        # Contract: login blocked until re-approved -> force logout
        logout(request)
        messages.success(request, "Profile updated. Your account is pending re-approval.")
        return redirect("login")

    return render(
        request,
        "board/employer_profile_edit.html",
        {"sitesettings": ss, "form": form, "employer": employer},
    )



@login_required
def jobseeker_profile_edit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    js = request.user.jobseeker
    form = JobSeekerProfileEditForm(request.POST or None, request.FILES or None, instance=js)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/jobseeker_profile_edit.html",
        {"sitesettings": ss, "form": form, "jobseeker": js},
    )


# ============================================================
# Packages + checkout
# ============================================================

def package_list(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    packages = PostingPackage.objects.filter(is_active=True).order_by("-priority_level", "price", "id")
    ctx = {"sitesettings": ss, "packages": packages}
    ctx.update(_gateway_context())
    return render(request, "board/package_list.html", ctx)


def buy_package(request: HttpRequest, package_id: int) -> HttpResponse:
    return redirect("checkout_select", package_id=package_id)


def checkout_select(request: HttpRequest, package_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('checkout_select', args=[package_id])}")

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)
    from .publication import pending_for
    intent=pending_for(request.user.employer,request.GET.get('publication'))
    ctx = {"sitesettings": _sitesettings(), "package": package,"publication":intent,"saved_jobs":Job.objects.filter(employer=request.user.employer,is_active=False).order_by('-posting_date','-id')}
    ctx.update(_gateway_context())
    return render(request, "checkout/checkout_select.html", ctx)


@login_required
def checkout_start(request: HttpRequest, package_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("checkout_select", package_id=package_id)

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    payment_method = (request.POST.get("payment_method") or "card").strip().lower()
    discount_code = (request.POST.get("discount_code") or "").strip()

    dc, final_amount, err = _apply_discount(package, discount_code)
    if err:
        messages.error(request, err)
        return redirect("checkout_select", package_id=package_id)

    gw = _gateway_context()

    if payment_method in ("card", "stripe"):
        secret = (gw.get("stripe_secret_key") or "").strip()
        if not secret or not gw.get("use_stripe"):
            messages.error(request, "Stripe is not configured.")
            return redirect("checkout_select", package_id=package_id)

        import stripe
        stripe.api_key = secret

        from .publication import checkout_request,checkout_idempotency_key
        try:
            publication=checkout_request(request,request.user.employer)
        except ValueError as exc:
            messages.error(request,str(exc))
            return redirect('checkout_select',package_id=package.pk)
        if publication and _available_credits(request.user.employer)>0:
            messages.info(request,'You already have a posting credit. Review this job and select Publish; no further payment is needed.')
            return redirect('job_edit',job_id=publication.job_id)
        amount_cents = int(round(final_amount * 100))

        try:
            session = stripe.checkout.Session.create(
                idempotency_key=checkout_idempotency_key(request,package,amount_cents,publication,dc.code if dc else ""),
                mode="payment",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "cad",
                            "product_data": {"name": package.name},
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=request.build_absolute_uri(reverse("checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=request.build_absolute_uri(reverse("checkout_select", args=[package.id]))+("?publication="+str(publication.pk) if publication else ""),
                metadata={
                    "employer_id": str(request.user.employer.id),
                    "package_id": str(package.id),
                    "discount_code": dc.code if dc else "",
                    "credits": str(package.credits),
                    "duration_days": str(package.duration_days),
                    "package_expires_days": str(package.package_expires_days),
                    "amount_cents": str(amount_cents),
                    "terms_version": "1",
                    "publication_request_id": str(publication.pk) if publication else "",
                    "publish_after_payment": "1" if publication else "0",
                },
            )
        except Exception:
            messages.error(request, "Unable to start Stripe checkout.")
            return redirect("checkout_select", package_id=package_id)

        if publication:
            from .models import JobPublicationRequest
            JobPublicationRequest.objects.filter(pk=publication.pk).update(checkout_session_id=session.id)
        return redirect(session.url)

    messages.error(request, "This payment method is unavailable. Please choose card payment.")
    return redirect("checkout_select", package_id=package_id)


@login_required
def checkout_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    employer = request.user.employer
    session_id = (request.GET.get("session_id") or "").strip()

    if not session_id:
        return redirect("package_list")

    gw = _gateway_context()
    secret = (gw.get("stripe_secret_key") or "").strip()
    if not secret or not gw.get("use_stripe"):
        messages.error(request, "Stripe is not configured.")
        return redirect("package_list")

    import stripe
    stripe.api_key = secret

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        messages.error(request, "Unable to verify Stripe payment session.")
        return redirect("package_list")

    if getattr(session, "payment_status", None) != "paid":
        messages.error(request, "Payment not completed.")
        return redirect("package_list")

    md = getattr(session, "metadata", {}) or {}

    try:
        session_employer_id = int(md.get("employer_id") or 0)
    except (TypeError, ValueError):
        session_employer_id = 0

    if session_employer_id != employer.id:
        messages.error(request, "This payment session does not belong to your employer account.")
        return redirect("package_list")

    from .payments import fulfill_checkout, InvalidCheckout
    try:
        invoice, package, created = fulfill_checkout(session, session_id=session_id, expected_employer_id=employer.pk)
    except InvalidCheckout:
        messages.error(request, "Unable to apply this payment. Please contact support with your payment reference.")
        return redirect("package_list")

    request.session.pop('credit_checkout_token',None)
    from .models import JobPublicationRequest
    publication=JobPublicationRequest.objects.filter(invoice=invoice,employer=employer).select_related('job').first()
    saved_jobs=Job.objects.filter(employer=employer,is_active=False).order_by('-posting_date','-id')
    published_job=publication.job if publication and publication.status=='published' else None
    pending_job=publication.job if publication and publication.status in ('ready','review') else None
    return render(request,'checkout/checkout_success.html',{
        'sitesettings':_sitesettings(),'package':package,'published_job':published_job,'publication':publication,
        'pending_job':pending_job,'saved_jobs':saved_jobs,'credits_available':_available_credits(employer),
    })



@login_required
def paypal_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    messages.error(request, "No PayPal payment has been verified. Please use card checkout.")
    return redirect("package_list")


@require_POST
@login_required
def stripe_create_session(request: HttpRequest, package_id: int) -> JsonResponse:
    if not hasattr(request.user, "employer"):
        return JsonResponse({"error": "Employer login required."}, status=403)

    if not _enforce_approval_or_logout(request):
        return JsonResponse({"error": "Approval required."}, status=403)

    employer = request.user.employer
    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    gw = _gateway_context()
    secret = (gw.get("stripe_secret_key") or "").strip()
    if not secret or not gw.get("use_stripe"):
        return JsonResponse({"error": "Stripe is not configured."}, status=400)

    discount_code = (request.POST.get("discount_code") or "").strip()
    dc, final_amount, err = _apply_discount(package, discount_code)
    if err:
        return JsonResponse({"error": err}, status=400)

    import stripe
    stripe.api_key = secret

    from .publication import checkout_request,checkout_idempotency_key
    try:publication=checkout_request(request,request.user.employer)
    except ValueError as exc:
        return JsonResponse({'error':str(exc)},status=400)
    if publication and _available_credits(request.user.employer)>0:
        return JsonResponse({'error':'A posting credit is already available. Publish your saved job without another payment.','job_url':reverse('job_edit',args=[publication.job_id])},status=409)
    amount_cents = int(round(final_amount * 100))

    try:
        session = stripe.checkout.Session.create(
            idempotency_key=checkout_idempotency_key(request,package,amount_cents,publication,dc.code if dc else ""),
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {"name": package.name},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=request.build_absolute_uri(reverse("checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("checkout_select", args=[package.id]))+("?publication="+str(publication.pk) if publication else ""),
            metadata={
                "employer_id": str(employer.id),
                "package_id": str(package.id),
                "discount_code": dc.code if dc else "",
                    "credits": str(package.credits),
                    "duration_days": str(package.duration_days),
                    "package_expires_days": str(package.package_expires_days),
                    "amount_cents": str(amount_cents),
                    "terms_version": "1",
                    "publication_request_id": str(publication.pk) if publication else "",
                    "publish_after_payment": "1" if publication else "0",
            },
        )
    except Exception:
        return JsonResponse({"error": "Unable to start Stripe checkout."}, status=500)

    if publication:
        from .models import JobPublicationRequest
        JobPublicationRequest.objects.filter(pk=publication.pk).update(checkout_session_id=session.id)
    return JsonResponse({"id": session.id})


# ============================================================
# Invoices
# ============================================================

@login_required
def invoice_detail(request: HttpRequest, invoice_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    employer = request.user.employer
    invoice = get_object_or_404(Invoice, id=invoice_id, employer=employer)

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "sitesettings": _sitesettings(),
            "invoice": invoice,
            "employer": employer,
        },
    )


@login_required
def invoice_download(request: HttpRequest, invoice_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied
    return redirect("invoice_detail", invoice_id=invoice_id)


# ============================================================
# Admin dashboard (embedded)
# ============================================================

@login_required
@xframe_options_exempt
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        raise PermissionDenied

    today = timezone.localdate()
    period = request.GET.get("period", "today")

    if period == "7":
        start = today - timedelta(days=6)
        end = today
    elif period == "30":
        start = today - timedelta(days=29)
        end = today
    elif period == "custom":
        try:
            start = date.fromisoformat(request.GET.get("start", ""))
            end = date.fromisoformat(request.GET.get("end", ""))
        except ValueError:
            start = end = today
        if start > end:
            start, end = end, start
    else:
        period = "today"
        start = end = today

    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), datetime.min.time()))

    paid_invoices = Invoice.objects.filter(
        status="paid",
        order_date__gte=start_dt,
        order_date__lt=end_dt,
    )

    context = {
        "sitesettings": _sitesettings(),
        "period": period,
        "start": start,
        "end": end,
        "jobs_posted": Job.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
        "applications_sent": Application.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
        "sales_count": paid_invoices.count(),
        "sales_total": (paid_invoices.aggregate(total=Sum("amount"))["total"] or 0) / 100,
        "employers_new": Employer.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
        "jobseekers_new": JobSeeker.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
        "alerts_created": JobAlert.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count(),
        "pending_employers": Employer.objects.filter(is_approved=False).order_by("-created_at", "-id")[:10],
        "pending_jobseekers": JobSeeker.objects.filter(is_approved=False).order_by("-created_at", "-id")[:10],
        "recent_paid_invoices": Invoice.objects.filter(status="paid").select_related("employer").order_by("-order_date", "-id")[:10],
    }
    return render(request, "admin/dashboard.html", context)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    import logging
    import stripe
    from .payments import fulfill_checkout, InvalidCheckout
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return HttpResponse(status=503)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""), secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    if event["type"] not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return HttpResponse(status=200)
    session = event["data"]["object"]
    if session.get("payment_status") != "paid":
        return HttpResponse(status=200)
    metadata = session.get("metadata") or {}
    if not metadata.get("employer_id") or not metadata.get("package_id"):
        return HttpResponse(status=200)  # Other products in the same Stripe account.
    try:
        fulfill_checkout(session)
    except Exception:
        logging.getLogger(__name__).exception("Stripe fulfilment failed; webhook should retry")
        return HttpResponse(status=500)
    return HttpResponse(status=200)


def job_alert_unsubscribe(request, token):
    from django.core import signing
    from django.http import Http404
    try:
        data = signing.loads(token, salt='board.job-alert-unsubscribe')
        alert = get_object_or_404(JobAlert, pk=data['id'], email=data['email'])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise Http404
    if request.method == 'POST':
        JobAlert.objects.filter(email=alert.email).update(active=False)
        return render(request, 'board/job_alert_unsubscribe.html', {'unsubscribed': True})
    if request.method != 'GET':
        return HttpResponse(status=405)
    return render(request, 'board/job_alert_unsubscribe.html', {'alert': alert})
