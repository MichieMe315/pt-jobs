from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Employer, JobSeeker

User = get_user_model()


def _activate_user(user: User) -> None:
    """
    Activate the related auth user if they're not active yet.
    Safe to call repeatedly; it only writes when needed.
    """
    if user and not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])


@receiver(post_save, sender=Employer)
def employer_auto_activate_user(sender, instance: Employer, **kwargs) -> None:
    """
    When an Employer is approved in Admin, auto-activate their login.
    """
    try:
        if getattr(instance, "is_approved", False) and getattr(instance, "user", None):
            _activate_user(instance.user)
    except Exception:
        # Never explode from a signal; keep admin smooth.
        pass


@receiver(post_save, sender=JobSeeker)
def jobseeker_auto_activate_user(sender, instance: JobSeeker, **kwargs) -> None:
    """
    When a JobSeeker is approved in Admin, auto-activate their login.
    """
    try:
        if getattr(instance, "is_approved", False) and getattr(instance, "user", None):
            _activate_user(instance.user)
    except Exception:
        # Never explode from a signal; keep admin smooth.
        pass
