from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        from . import signals  # noqa: F401
        from .startup_import import startup_tasks  # noqa: F401
        startup_tasks()
