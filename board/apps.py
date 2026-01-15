# board/apps.py
from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401

        # Startup bulk import (only runs when env var is enabled)
        from .startup_import import run_bulk_import_if_enabled  # noqa: F401

        run_bulk_import_if_enabled()
