from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"

    def ready(self):
        # Import signals so they are registered at startup
        from . import signals  # noqa: F401
