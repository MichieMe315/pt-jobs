from django.core.mail import send_mail
from django.conf import settings

def safe_send(subject, message, to):
    if not to:
        return
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost")
    try:
        send_mail(subject, message, from_email, [to], fail_silently=True)
    except Exception:
        # swallow in dev
        pass
