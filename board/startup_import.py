import os
import sys
from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError


def run_employer_import_if_enabled() -> None:
    if os.environ.get("RUN_EMPLOYER_IMPORT_ON_STARTUP") != "1":
        return

    blocked = {"migrate", "makemigrations", "collectstatic", "shell", "createsuperuser"}
    if any(cmd in sys.argv for cmd in blocked):
        return

    csv_rel = os.environ.get("EMPLOYER_IMPORT_CSV_PATH", "board/data/employers.csv")
    csv_path = Path(settings.BASE_DIR) / csv_rel

    if not csv_path.exists():
        print(f"[EMPLOYER IMPORT] SKIP: CSV not found at {csv_path}")
        return

    try:
        from board.models import Employer
    except Exception as e:
        print(f"[EMPLOYER IMPORT] SKIP: model import failed: {e}")
        return

    try:
        if Employer.objects.exists():
            print("[EMPLOYER IMPORT] SKIP: Employers already exist.")
            return
    except (OperationalError, ProgrammingError) as e:
        print(f"[EMPLOYER IMPORT] SKIP: DB not ready: {e}")
        return

    try:
        from board.management.commands.import_employers_csv import Command

        print(f"[EMPLOYER IMPORT] RUNNING from {csv_path}")
        Command().handle(csv_path=str(csv_path), dry_run=False)
        print("[EMPLOYER IMPORT] DONE")
    except Exception as e:
        # CRITICAL: do not kill the web process
        print(f"[EMPLOYER IMPORT] ERROR (non-fatal): {e}")
        return
