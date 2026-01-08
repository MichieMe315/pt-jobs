# board/apps.py
from __future__ import annotations

import threading

from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401

        # Startup imports (run in a short delayed thread so app can finish loading)
        from .startup_import import run_bulk_import_if_enabled  # noqa

        threading.Timer(2.0, run_bulk_import_if_enabled).start()
