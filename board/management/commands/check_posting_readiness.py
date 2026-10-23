"""Read-only configuration check for reliable payment confirmation."""
from urllib.parse import urlsplit
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.urls import reverse

class Command(BaseCommand):
 help='Check paid-posting webhook configuration without changing jobs, credits, payments or Stripe settings.'
 def add_arguments(self,p):p.add_argument('--verify-stripe',action='store_true',help='Also read Stripe webhook registrations to verify the production URL and enabled checkout event.')
 def handle(self,*a,**o):
  import os
  from board.views import _gateway_context
  gw=_gateway_context()
  self.stdout.write('Deployed commit: '+os.environ.get('RAILWAY_GIT_COMMIT_SHA','Local development'))
  if not getattr(settings,'STRIPE_WEBHOOK_SECRET','').strip():raise CommandError('STRIPE_WEBHOOK_SECRET is missing. Configure the signing secret for the PTJC /stripe/webhook/ endpoint; do not paste it into chat.')
  if not gw.get('use_stripe') or not gw.get('stripe_secret_key'):raise CommandError('Stripe card checkout is not configured.')
  path=reverse('stripe_webhook');self.stdout.write('Signing secret configured. Webhook route: '+path)
  if o['verify_stripe']:
   import stripe
   stripe.api_key=gw['stripe_secret_key']
   try:items=list(stripe.WebhookEndpoint.list(limit=100).auto_paging_iter())
   except Exception:raise CommandError('Could not read Stripe webhook registrations. Check API key permissions in Stripe. No records changed.')
   host=urlsplit(getattr(settings,'SITE_URL','https://physiotherapyjobscanada.ca')).hostname
   matches=[e for e in items if e.get('status')=='enabled' and urlsplit(e.get('url','')).hostname==host and urlsplit(e.get('url','')).path.rstrip('/')==path.rstrip('/') and ('*' in e.get('enabled_events',[]) or 'checkout.session.completed' in e.get('enabled_events',[]))]
   if not matches:raise CommandError('No enabled PTJC Stripe webhook for checkout.session.completed was found. Configure it before relying on browser-independent payment confirmation.')
   self.stdout.write('Stripe endpoint registered and enabled for completed checkout. Matching signing secrets still require a successful signed delivery.')
  self.stdout.write(self.style.SUCCESS('Posting configuration check passed. No records changed.'))
