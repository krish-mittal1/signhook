"""Stripe webhook provider.

Generates Event envelopes shaped like Stripe's webhook payloads and signs them
with the official ``Stripe-Signature`` scheme:

    Stripe-Signature: t=<unix_ts>,v1=<hex>

    v1 = HMAC-SHA256(webhook_secret, "{t}.{raw_json_body}")

Reference:
https://docs.stripe.com/webhooks/signatures
"""

from __future__ import annotations

import secrets
from typing import Any, Callable

from utils.payload_templates import fake_id, unix_timestamp
from utils.signing import canonical_json, hmac_sha256_hex

# Align loosely with a current Stripe API version; fixtures are synthetic.
STRIPE_API_VERSION = "2024-06-20"

EVENT_TYPES = [
    "payment_intent.succeeded",
    "customer.created",
    "invoice.paid",
]


def generate_payload(event_type: str) -> dict[str, Any]:
    """Return a realistic Stripe ``event`` object for ``event_type``.

    Raises:
        ValueError: if ``event_type`` is not in ``EVENT_TYPES``.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unsupported Stripe event_type {event_type!r}. "
            f"Expected one of: {', '.join(EVENT_TYPES)}"
        )

    builder = _OBJECT_BUILDERS[event_type]
    created = unix_timestamp()
    return {
        "id": fake_id("evt"),
        "object": "event",
        "api_version": STRIPE_API_VERSION,
        "created": created,
        "type": event_type,
        "livemode": False,
        "pending_webhooks": 1,
        "request": {
            "id": fake_id("req"),
            "idempotency_key": None,
        },
        "data": {
            "object": builder(created),
        },
    }


def sign_payload(
    payload: dict[str, Any],
    secret: str,
    *,
    target_url: str | None = None,
) -> dict[str, str]:
    """Sign ``payload`` and return headers a Stripe webhook would send.

    ``target_url`` is ignored (Stripe signs the body only). Kept on the
    callable so every provider module shares one signature shape.
    """
    _ = target_url
    if not secret:
        raise ValueError("Stripe webhook signing secret must be non-empty")

    timestamp = unix_timestamp()
    body = canonical_json(payload)
    signature = hmac_sha256_hex(secret, f"{timestamp}.{body}")
    return {"Stripe-Signature": f"t={timestamp},v1={signature}"}


# ---------------------------------------------------------------------------
# Nested data.object builders — fields Stripe actually delivers
# ---------------------------------------------------------------------------


def _payment_intent(created: int) -> dict[str, Any]:
    pi_id = fake_id("pi")
    return {
        "id": pi_id,
        "object": "payment_intent",
        "amount": 2000,
        "amount_capturable": 0,
        "amount_received": 2000,
        "currency": "usd",
        "status": "succeeded",
        "created": created,
        "customer": fake_id("cus", nbytes=8),
        "description": "Webhook sandbox test payment",
        "livemode": False,
        "metadata": {"source": "webhook-sandbox"},
        "payment_method": fake_id("pm", nbytes=8),
        "payment_method_types": ["card"],
        "receipt_email": "customer@example.com",
        "capture_method": "automatic",
        "confirmation_method": "automatic",
        "client_secret": f"{pi_id}_secret_{secrets.token_hex(8)}",
    }


def _customer(created: int) -> dict[str, Any]:
    return {
        "id": fake_id("cus", nbytes=8),
        "object": "customer",
        "created": created,
        "email": "customer@example.com",
        "name": "Ada Lovelace",
        "description": "Webhook sandbox test customer",
        "livemode": False,
        "metadata": {"source": "webhook-sandbox"},
        "phone": None,
        "currency": "usd",
        "default_source": None,
        "invoice_prefix": secrets.token_hex(3).upper(),
        "invoice_settings": {
            "custom_fields": None,
            "default_payment_method": None,
            "footer": None,
            "rendering_options": None,
        },
        "balance": 0,
        "delinquent": False,
        "tax_exempt": "none",
    }


def _invoice(created: int) -> dict[str, Any]:
    customer_id = fake_id("cus", nbytes=8)
    invoice_id = fake_id("in")
    return {
        "id": invoice_id,
        "object": "invoice",
        "created": created,
        "customer": customer_id,
        "customer_email": "customer@example.com",
        "customer_name": "Ada Lovelace",
        "currency": "usd",
        "status": "paid",
        "paid": True,
        "amount_due": 4900,
        "amount_paid": 4900,
        "amount_remaining": 0,
        "subtotal": 4900,
        "total": 4900,
        "livemode": False,
        "metadata": {"source": "webhook-sandbox"},
        "billing_reason": "subscription_cycle",
        "collection_method": "charge_automatically",
        "number": f"WSAND-{created}",
        "payment_intent": fake_id("pi"),
        "subscription": fake_id("sub", nbytes=8),
        "hosted_invoice_url": (
            f"https://invoice.stripe.com/i/acct_sandbox/{invoice_id}"
        ),
        "invoice_pdf": f"https://pay.stripe.com/invoice/{invoice_id}/pdf",
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": fake_id("il"),
                    "object": "line_item",
                    "amount": 4900,
                    "currency": "usd",
                    "description": "Webhook Sandbox Pro (Monthly)",
                    "quantity": 1,
                    "type": "subscription",
                }
            ],
            "has_more": False,
            "total_count": 1,
            "url": f"/v1/invoices/{invoice_id}/lines",
        },
    }


_OBJECT_BUILDERS: dict[str, Callable[[int], dict[str, Any]]] = {
    "payment_intent.succeeded": _payment_intent,
    "customer.created": _customer,
    "invoice.paid": _invoice,
}
