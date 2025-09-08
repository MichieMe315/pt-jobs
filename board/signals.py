from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.mail import send_mail
from .models import JobSeeker, Employer, Job

ADMIN_NOTIFY_EMAIL = None  # set to an admin email string if you want real mail

def _admin_email():
    return ADMIN_NOTIFY_EMAIL or "admin@example.com"

@receiver(post_save, sender=JobSeeker)
def notify_admin_new_jobseeker(sender, instance: JobSeeker, created, **kwargs):
    if not created:
        return
    subject = "New Job Seeker registration"
    name = instance.full_name or instance.email
    body = f"A new job seeker has registered:\n\nName: {name}\nEmail: {instance.email}\nStatus: {instance.registration_status}\n"
    try:
        send_mail(subject, body, _admin_email(), [_admin_email()], fail_silently=True)
    except Exception:
        pass

@receiver(post_save, sender=Employer)
def notify_admin_new_employer(sender, instance: Employer, created, **kwargs):
    if not created:
        return
    subject = "New Employer registration"
    who = instance.company_name or instance.name or instance.email
    body = f"Employer registered: {who} ({instance.email})"
    try:
        send_mail(subject, body, _admin_email(), [_admin_email()], fail_silently=True)
    except Exception:
        pass

@receiver(post_save, sender=Job)
def notify_admin_new_job(sender, instance: Job, created, **kwargs):
    if not created:
        return
    subject = "New Job posted"
    body = f"Job: {instance.title} by {instance.employer}"
    try:
        send_mail(subject, body, _admin_email(), [_admin_email()], fail_silently=True)
    except Exception:
        pass
