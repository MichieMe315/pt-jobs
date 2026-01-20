from __future__ import annotations

import os
import requests
from django.core.mail.backends.base import BaseEmailBackend


class SendGridAPIBackend(BaseEmailBackend):
    """
    Django EmailBackend that sends via SendGrid Web API (HTTPS).
    Requires env var SENDGRID_API_KEY.
    """

    def send_messages(self, email_messages):
        api_key = os.environ.get("SENDGRID_API_KEY") or ""
        if not api_key or not email_messages:
            return 0

        sent = 0
        for msg in email_messages:
            try:
                from_email = msg.from_email or os.environ.get("DEFAULT_FROM_EMAIL") or ""
                to_emails = []
                for to in (msg.to or []):
                    if to:
                        to_emails.append({"email": to})

                if not from_email or not to_emails:
                    continue

                # Prefer HTML if provided, else use body as plain text.
                body_text = msg.body or ""
                html_body = None
                if getattr(msg, "alternatives", None):
                    for alt, mimetype in msg.alternatives:
                        if mimetype == "text/html":
                            html_body = alt
                            break

                content = []
                if html_body is not None:
                    content.append({"type": "text/html", "value": html_body})
                else:
                    content.append({"type": "text/plain", "value": body_text})

                payload = {
                    "personalizations": [{"to": to_emails, "subject": msg.subject or ""}],
                    "from": {"email": from_email},
                    "content": content,
                }

                r = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=15,
                )

                # 202 Accepted = success
                if r.status_code == 202:
                    sent += 1
                else:
                    if not self.fail_silently:
                        raise RuntimeError(f"SendGrid failed: {r.status_code} {r.text}")
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
