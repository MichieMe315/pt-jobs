from __future__ import annotations

from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError, ProgrammingError

from .models import Employer, JobSeeker, SiteSettings


# ---------------------------------------------------------
# Site settings helper (used by views)
# ---------------------------------------------------------


def get_settings() -> Optional[SiteSettings]:
    """
    Safe helper for views to grab the singleton SiteSettings instance.
    Mirrors the safety of the context processor: never crash if the
    table/columns aren't ready (migrations).
    """
    try:
        return SiteSettings.objects.first()
    except (OperationalError, ProgrammingError, ImproperlyConfigured):
        return None


# ---------------------------------------------------------
# Role helpers
# ---------------------------------------------------------


def require_employer(user: User) -> bool:
    """
    Return True only if the user has an Employer profile AND is approved.
    Used by employer-only views (dashboard, post job, etc.).
    """
    if not user.is_authenticated:
        return False

    try:
        employer = user.employer
    except Employer.DoesNotExist:
        return False

    # Only allow approved employers
    return bool(employer.is_approved)


def require_jobseeker(user: User) -> bool:
    """
    Return True only if the user has a JobSeeker profile.
    (JobSeeker model in this project doesn't have an is_approved flag.)
    """
    if not user.is_authenticated:
        return False

    try:
        _ = user.jobseeker
    except JobSeeker.DoesNotExist:
        return False

    return True
