from django.conf import settings
from django.core.mail import EmailMultiAlternatives, mail_admins
from django.template import Template, Context

from .models import EmailTemplate, SiteSettings


def _get_from_email() -> str:
    """
    Resolve the from-email.

    1. If SiteSettings has a brand_email (optional future field), use that.
    2. Otherwise, use settings.DEFAULT_FROM_EMAIL if set.
    3. Fallback to 'webmaster@localhost'.
    """
    try:
        ss = SiteSettings.objects.order_by("-id").first()
        if ss and getattr(ss, "brand_email", None):
            return ss.brand_email
    except Exception:
        pass

    return getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost")


def _get_emailtemplate(email_key: str):
    """
    Return enabled template by key, or None if missing/disabled.
    Keep this tolerant because your schema has changed over time.
    """
    try:
        return EmailTemplate.objects.get(key=email_key, is_enabled=True)
    except Exception:
        return None


def _render_template_string(template_str: str, context: dict) -> str:
    return Template(template_str).render(Context(context))


def render_email_template(email_key: str, context: dict) -> tuple[str, str]:
    """
    Load an EmailTemplate by key, fallback to simple default values.

    IMPORTANT: Supports both historical fields:
      - html (newer)
      - body (older)
    """
    tmpl = _get_emailtemplate(email_key)
    if not tmpl:
        # graceful fallback so code never crashes if template is missing
        return f"[Missing EmailTemplate: {email_key}]", "No template found."

    subject_raw = getattr(tmpl, "subject", "") or ""
    # Prefer html if present; fallback to body if present.
    body_raw = getattr(tmpl, "html", None)
    if body_raw is None:
        body_raw = getattr(tmpl, "body", "")

    subject = _render_template_string(subject_raw, context)
    body = _render_template_string(body_raw or "", context)
    return subject, body


def send_templated_email(email_key: str, to_list: list[str], context: dict) -> None:
    """
    Send an email using EmailTemplate stored in admin.
    - If template has html, send as HTML alternative.
    - If not, send plain text.
    """
    if not to_list:
        return

    from_email = _get_from_email()

    tmpl = _get_emailtemplate(email_key)
    subject, rendered = render_email_template(email_key, context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=rendered,
        from_email=from_email,
        to=to_list,
    )

    # If template has explicit html field, attach as HTML alternative.
    if tmpl is not None and getattr(tmpl, "html", None):
        html_rendered = _render_template_string(tmpl.html or "", context)
        msg.attach_alternative(html_rendered, "text/html")

    msg.send(fail_silently=True)


def notify_admins(email_key: str, context: dict) -> None:
    """
    Use EmailTemplate for admin notifications (subject/body come from admin).
    """
    subject, body = render_email_template(email_key, context)
    mail_admins(subject, body, fail_silently=True)
