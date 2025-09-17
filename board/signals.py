from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import JobSeeker, Employer

@receiver(post_save, sender=JobSeeker)
def notify_admin_new_jobseeker(sender, instance: JobSeeker, created, **kwargs):
    if not created:
        return
    subject = "New Job Seeker Signup"
    name = instance.full_name  # safe property on the model
    body = f"A new job seeker signed up:\n\nName: {name}\nEmail: {instance.email}\nLocation: {instance.current_location}\n"
    send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [a[1] for a in settings.ADMINS] if hasattr(settings, "ADMINS") else [instance.email])

@receiver(post_save, sender=Employer)
def notify_admin_new_employer(sender, instance: Employer, created, **kwargs):
    if not created:
        return
    subject = "New Employer Signup"
    company = instance.company_name or instance.name
    body = f"A new employer signed up:\n\nCompany: {company}\nEmail: {instance.email}\nLocation: {instance.location}\n"
    send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [a[1] for a in settings.ADMINS] if hasattr(settings, "ADMINS") else [instance.email])
