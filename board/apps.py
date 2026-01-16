# board/apps.py
from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401

        # Startup tasks (all gated by env vars; safe to leave code deployed)
        from .startup_import import (
            ensure_superuser_if_enabled,
            run_wipe_if_enabled,
            run_bulk_import_if_enabled,
        )

        ensure_superuser_if_enabled()
        run_wipe_if_enabled()
        run_bulk_import_if_enabled()
