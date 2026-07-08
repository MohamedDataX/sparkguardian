"""Stripe billing — checkout sessions + webhook handling.

Test-mode ready: set STRIPE_SECRET_KEY / STRIPE_PRICE_ID / STRIPE_WEBHOOK_SECRET
to your Stripe *test* keys. When keys are absent the routes return 501 so the
rest of the app keeps working.
"""
from __future__ import annotations

from backend.config import settings

try:
    import stripe
except ImportError:  # SDK optional until billing is used
    stripe = None  # type: ignore[assignment]


def _client() -> "stripe":  # type: ignore[valid-type]
    if stripe is None:
        raise RuntimeError("stripe SDK not installed — `pip install stripe`")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_session(email: str) -> str:
    """Create a subscription Checkout Session, return its hosted URL."""
    client = _client()
    session = client.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url=f"{settings.PUBLIC_URL}/?checkout=success",
        cancel_url=f"{settings.PUBLIC_URL}/?checkout=cancel",
        metadata={"email": email},
    )
    return session.url


def parse_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify Stripe signature and return the event object."""
    client = _client()
    return client.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
