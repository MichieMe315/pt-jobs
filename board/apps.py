from django.apps import AppConfig
import threading


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        from . import signals  # noqa: F401

        # Run importer shortly after app boot (web container), non-blocking.
        def _delayed_import():
            from .startup_import import run_employer_import_if_enabled
            run_employer_import_if_enabled()

        threading.Timer(3.0, _delayed_import).start()
