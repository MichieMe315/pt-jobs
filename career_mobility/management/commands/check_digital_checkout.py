from django.core.management.base import BaseCommand,CommandError
from career_mobility.store_config import stripe_key,webhook_secret
from career_mobility.store_access import workbook_product
class Command(BaseCommand):
    help='Check digital checkout configuration without displaying secrets or charging a card.'
    def add_arguments(self,parser):parser.add_argument('--probe',action='store_true',help='Make a read-only Stripe account lookup.')
    def handle(self,*args,**options):
        key=stripe_key();secret=webhook_secret();p=workbook_product()
        self.stdout.write('Stripe API key: '+('configured' if key else 'MISSING'))
        self.stdout.write('Digital webhook signing secret: '+('configured' if secret else 'MISSING'))
        self.stdout.write('Workbook price: CAD '+str(p.price_cad))
        if options['probe']:
            if not key:raise CommandError('Configure an API key before probing.')
            try:
                import stripe
                stripe.Account.retrieve(api_key=key)
            except Exception as exc:raise CommandError('Stripe connection failed: '+type(exc).__name__) from None
            self.stdout.write('Stripe connection accepted. No payment was made.')
        if not key or not secret:raise CommandError('Digital checkout is not ready. The existing PT Jobs API key can be reused; add the endpoint-specific webhook secret.')
        self.stdout.write('Configuration present. A real payment and webhook test is still required.')
