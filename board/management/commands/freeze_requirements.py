import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Freeze current environment packages into requirements.txt (like `pip freeze > requirements.txt`)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--outfile",
            type=str,
            default="requirements.txt",
            help="Relative path (from project root) to write requirements. Default: requirements.txt",
        )

    def handle(self, *args, **options):
        # Determine output path (project root)
        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        out_rel = options["outfile"]
        out_path = (base_dir / out_rel).resolve()

        # Ensure parent directories exist
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self.stdout.write(self.style.HTTP_INFO(f"Freezing packages to: {out_path}"))

        # Run pip freeze using the current Python interpreter
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CommandError(
                f"pip freeze failed with code {e.returncode}:\n{e.stderr}"
            )

        frozen = proc.stdout.strip().splitlines()
        if not frozen:
            self.stdout.write(self.style.WARNING("No packages found in the current environment."))

        # Write the file
        out_path.write_text("\n".join(frozen) + "\n", encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(frozen)} lines to {out_path}"))
        self.stdout.write(self.style.SUCCESS("Done."))
