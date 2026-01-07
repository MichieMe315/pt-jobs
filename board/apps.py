from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401

        # Optional: one-time deploy-time import (no shell required)
        # Controlled by env var RUN_EMPLOYER_IMPORT_ON_STARTUP=1
        try:
            from .startup_import import run_employer_import_if_enabled
            run_employer_import_if_enabled()
        except Exception:
            # Let errors surface in logs so you can see them during deploy
            raise
