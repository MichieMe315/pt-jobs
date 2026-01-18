from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"

    def ready(self):
        # IMPORTANT:
        # We only run the startup import when explicitly enabled by env var,
        # and we skip during migrate/collectstatic to avoid boot issues.
        try:
            from .startup_import import run_startup_tasks_if_enabled
            run_startup_tasks_if_enabled()
        except Exception:
            # Never crash the app during startup
            return
