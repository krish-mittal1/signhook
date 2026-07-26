"""Provider registry — maps provider ids to modules and event type lists.

Real generate/sign wiring comes in later steps; mocks are fine for Step 1.
"""

from __future__ import annotations

from typing import Any

from . import github, stripe, twilio

ProviderModule = Any

PROVIDERS: dict[str, ProviderModule] = {
    "stripe": stripe,
    "twilio": twilio,
    "github": github,
}

PROVIDER_META: list[dict[str, Any]] = [
    {
        "id": "stripe",
        "name": "Stripe",
        "event_types": list(stripe.EVENT_TYPES),
    },
    {
        "id": "twilio",
        "name": "Twilio",
        "event_types": list(twilio.EVENT_TYPES),
    },
    {
        "id": "github",
        "name": "GitHub",
        "event_types": list(github.EVENT_TYPES),
    },
]


def get_provider(provider_id: str) -> ProviderModule:
    try:
        return PROVIDERS[provider_id]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {provider_id}") from exc


def generate_payload(provider_id: str, event_type: str) -> dict[str, Any]:
    return get_provider(provider_id).generate_payload(event_type)


def sign_payload(
    provider_id: str,
    payload: dict[str, Any],
    secret: str,
    *,
    target_url: str | None = None,
) -> dict[str, str]:
    return get_provider(provider_id).sign_payload(payload, secret, target_url=target_url)
