# board/apps.py
from __future__ import annotations

from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "board"

    def ready(self):
        # Keep startup work safe; never crash the worker.
        from .startup_import import safe_startup_tasks

        safe_startup_tasks()
