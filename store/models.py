from __future__ import annotations

from django.db import models
from django.conf import settings


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    company_name = models.CharField(max_length=200, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    total_cents = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")

    stripe_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} — {self.get_status_display()} — ${self.total_cents/100:.2f}"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.CASCADE)
    package = models.ForeignKey("board.PostingPackage", on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    unit_price_cents = models.PositiveIntegerField()

    def line_total_cents(self) -> int:
        return self.qty * self.unit_price_cents

    def __str__(self) -> str:
        return f"{self.package.name} x{self.qty}"


class Discount(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)

    percent_off = models.PositiveIntegerField(null=True, blank=True)        # 0..100
    amount_off_cents = models.PositiveIntegerField(null=True, blank=True)   # absolute

    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    uses = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class PaymentMethod(models.Model):
    PROVIDER_CHOICES = [
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
    ]
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    display_name = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=False)
    live_mode = models.BooleanField(default=False)

    # Store non-sensitive config (e.g., publishable keys, account IDs). Keep secrets in env.
    config = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "live_mode")
        ordering = ["provider", "-live_mode"]

    def __str__(self) -> str:
        mode = "Live" if self.live_mode else "Test"
        return f"{self.get_provider_display()} ({mode})"
