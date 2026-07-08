"""Stripe billing endpoints — checkout + webhook."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend import billing, service
from backend.config import settings
from backend.schemas import CheckoutRequest, CheckoutResponse

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest) -> CheckoutResponse:
    """Start a Pro subscription. Returns the Stripe-hosted checkout URL."""
    if not settings.stripe_enabled:
        # Architecture is wired; keys just aren't set. TODO: add Stripe test keys.
        raise HTTPException(status_code=501, detail="Billing not configured (set STRIPE_* env vars).")
    try:
        url = billing.create_checkout_session(str(req.email))
    except Exception as exc:  # surface Stripe errors cleanly
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc
    return CheckoutResponse(url=url)


@router.post("/webhook")
async def webhook(request: Request) -> dict[str, str]:
    """Stripe webhook — issues a Pro license once a subscription is paid."""
    if not settings.stripe_enabled:
        raise HTTPException(status_code=501, detail="Billing not configured.")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = billing.parse_webhook(payload, sig)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {exc}") from exc

    if event["type"] == "checkout.session.completed":
        obj = event["data"]["object"]
        email = (obj.get("metadata") or {}).get("email") or obj.get("customer_email")
        if email:
            service.create_license(
                name=email.split("@")[0],
                email=email,
                kind="monthly",
                stripe_customer=obj.get("customer"),
                stripe_sub=obj.get("subscription"),
            )
    return {"status": "ok"}
