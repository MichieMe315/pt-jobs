import os
import json
import urllib.request
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMessage


class SendGridAPIEmailBackend(BaseEmailBackend):
    """
    Send emails through SendGrid Web API (HTTPS).
    Use when SMTP ports are blocked (common on some hosts).
    """

    def send_messages(self, email_messages):
        api_key = os.environ.get("SENDGRID_API_KEY") or os.environ.get("EMAIL_HOST_PASSWORD")
        if not api_key:
            raise RuntimeError("Missing SENDGRID_API_KEY (or EMAIL_HOST_PASSWORD) for SendGrid API email backend.")

        sent = 0
        for message in email_messages:
            if not isinstance(message, EmailMessage):
                continue

            payload = {
                "personalizations": [{"to": [{"email": addr} for addr in message.to]}],
                "from": {"email": message.from_email},
                "subject": message.subject,
                "content": [{"type": "text/plain", "value": message.body or ""}],
            }

            # Optional HTML alternative
            if getattr(message, "alternatives", None):
                for alt_body, mimetype in message.alternatives:
                    if mimetype == "text/html":
                        payload["content"].append({"type": "text/html", "value": alt_body})

            req = urllib.request.Request(
                "https://api.sendgrid.com/v3/mail/send",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    # SendGrid returns 202 Accepted on success
                    if resp.status in (200, 202):
                        sent += 1
                    else:
                        raise RuntimeError(f"SendGrid API email failed: HTTP {resp.status}")
            except Exception as e:
                if self.fail_silently:
                    continue
                raise

        return sent
