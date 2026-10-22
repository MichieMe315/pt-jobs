"""A compact email frame; content remains controlled by existing templates."""
from django.utils.html import escape


def email_frame(title, body):
    return ('<!doctype html><html><body style="margin:0;background:#f1f2f4;color:#20252b;font-family:Arial,sans-serif">'
        '<div style="max-width:620px;margin:24px auto;background:#fff;border-top:4px solid #b72d38;padding:24px">'
        '<p style="font-size:13px;color:#62666c">Physiotherapy Jobs Canada</p>'
        f'<h1 style="font-size:21px;line-height:1.35">{escape(title)}</h1>{body}'
        '<p style="margin-top:24px;font-size:12px;color:#62666c">PhysiotherapyJobsCanada.ca</p></div></body></html>')


def profile_review_email(request, employer, recipients):
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.urls import reverse
    from .models import EmailTemplate
    from .views import send_templated_email
    key='admin_employer_profile_updated'
    url=request.build_absolute_uri(reverse('admin:board_employer_change',args=[employer.pk]))
    context={'email':employer.email,'company_name':employer.company_name,'review_url':url}
    if EmailTemplate.objects.filter(key=key).exists():
        return send_templated_email(key,recipients,context)
    if not recipients:return False
    subject='[PTJC] Employer profile needs review'
    text=f'{employer.company_name} ({employer.email}) updated their profile. Approval is required before access resumes. Review: {url}'
    message=EmailMultiAlternatives(subject,text,settings.DEFAULT_FROM_EMAIL,recipients,reply_to=[employer.email] if employer.email else None)
    message.attach_alternative(email_frame('Employer profile needs review',f'<p>{escape(employer.company_name)} · {escape(employer.email)}</p><p>Profile updated. Approval is required before access resumes.</p><p><a href="{escape(url)}">Review employer profile</a></p>'),'text/html')
    try:
        return bool(message.send(fail_silently=False))
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Employer review email failed')
        return False
