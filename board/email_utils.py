from typing import Iterable, Optional, Sequence, Tuple
from django.core.mail import EmailMessage, get_connection
from django.conf import settings

try:
    from .models import SiteEmailSettings
except Exception:
    SiteEmailSettings = None  # type: ignore


def _db_email_connection():
    """
    Build an SMTP connection from SiteEmailSettings if active; otherwise None.
    """
    if not SiteEmailSettings:
        return None

    cfg = SiteEmailSettings.get_active()
    if not cfg:
        return None

    backend = cfg.backend or "django.core.mail.backends.smtp.EmailBackend"
    return get_connection(
        backend=backend,
        host=cfg.host or None,
        port=cfg.port or None,
        username=cfg.host_user or None,
        password=cfg.host_password or None,
        use_tls=cfg.use_tls,
        use_ssl=cfg.use_ssl,
        timeout=20,
    )


def send_email(
    subject: str,
    body: str,
    to: Sequence[str],
    *,
    from_email: Optional[str] = None,
    attachments: Optional[Iterable[Tuple[str, bytes, str]]] = None,
    fail_silently: bool = True,
) -> int:
    """
    Sends an email using DB-configured SMTP if available, else falls back to settings.py.
    attachments: iterable of (filename, content_bytes, mimetype)
    """
    conn = _db_email_connection() or get_connection()
    from_addr = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_addr,
        to=list(filter(None, to)),
        connection=conn,
    )
    if attachments:
        for (name, content, mimetype) in attachments:
            msg.attach(name, content, mimetype or "application/octet-stream")
    return msg.send(fail_silently=fail_silently)
