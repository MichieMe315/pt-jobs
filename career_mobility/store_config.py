"""Reuse the existing Stripe account. Webhook secrets belong to their endpoints."""
import os
from django.conf import settings

def stripe_key():
    explicit=os.environ.get('PT_MOBILITY_STRIPE_SECRET_KEY','').strip()
    if explicit:return explicit
    from board.models import PaymentGatewayConfig
    cfg=PaymentGatewayConfig.get_active_gateway()
    if cfg and cfg.use_stripe and (cfg.stripe_secret_key or '').strip():return cfg.stripe_secret_key.strip()
    return (getattr(settings,'STRIPE_SECRET_KEY','') or os.environ.get('STRIPE_SECRET_KEY','')).strip()

def webhook_secret():return os.environ.get('PT_MOBILITY_STRIPE_WEBHOOK_SECRET','').strip()
