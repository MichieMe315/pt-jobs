from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"
    verbose_name = "Job Board"

    def ready(self) -> None:
        # Ensure signal receivers are registered
        from . import signals  # noqa: F401
