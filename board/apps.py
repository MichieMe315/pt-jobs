from django.apps import AppConfig
from django.db.models.signals import post_migrate


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401

        def _run_import(sender, **kwargs):
            from .startup_import import run_employer_import_if_enabled
            run_employer_import_if_enabled()

        post_migrate.connect(_run_import, sender=self)
