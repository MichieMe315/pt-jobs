from django.core.management import call_command
from django.core.management.base import BaseCommand
class Command(BaseCommand):
    help="Run scheduled source review and provincial fee checks; never auto-publish."
    def add_arguments(self, parser):
        parser.add_argument("--dry-run",action="store_true")
    def handle(self,*args,**opts):
        call_command("check_mobility_sources",**({"dry_run":True} if opts["dry_run"] else {}))
        for command in ("sync_official_licence_fees","sync_additional_pt_fees"):
            call_command(command,**({"dry_run":True} if opts["dry_run"] else {}))
        call_command("audit_licence_fees")
