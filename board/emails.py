from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template

from .models import EmailTemplate


def _render_template_string(s: str, context: Dict[str, Any]) -> str:
    if not s:
        return ""
    return Template(s).render(Context(context))


def send_templated_email(
    template_key: str,
    to_emails: Iterable[str],
    context: Optional[Dict[str, Any]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """
    Sends an email using EmailTemplate(key=template_key).
    Safe behavior:
    - If template missing/disabled -> no crash, returns False.
    """
    context = context or {}
    tpl = EmailTemplate.objects.filter(key=template_key).first()
    if not tpl or not getattr(tpl, "is_enabled", True):
        return False

    subject = _render_template_string(tpl.subject or "", context).strip()
    html_body = _render_template_string(tpl.html or "", context)
    text_body = _render_template_string(getattr(tpl, "text", "") or "", context)

    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"
    to_list = [e for e in to_emails if e]

    if not to_list:
        return False

    msg = EmailMultiAlternatives(subject=subject, body=text_body or "", from_email=from_email, to=to_list)
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    return True
