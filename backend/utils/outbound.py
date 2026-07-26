"""Build the exact outbound HTTP request for a signed webhook.

Critical invariant: the body bytes returned here are the same bytes the
provider's ``sign_payload`` HMAC'd (Stripe/GitHub) or the form params that
Twilio's signature covers. Never re-serialize after signing with a different
encoder.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from providers import sign_payload
from utils.signing import canonical_json

JSON_PROVIDERS = frozenset({"stripe", "github"})
FORM_PROVIDERS = frozenset({"twilio"})

SEND_TIMEOUT_SECONDS = 10.0


def prepare_outbound(
    provider: str,
    payload: dict[str, Any],
    secret: str,
    target_url: str,
) -> tuple[dict[str, str], bytes]:
    """Return ``(headers, body_bytes)`` ready for ``httpx`` POST.

    Raises:
        ValueError: unknown provider or signing validation failure.
    """
    if provider in JSON_PROVIDERS:
        # Sign first — Stripe/GitHub HMAC the canonical JSON string internally.
        headers = sign_payload(provider, payload, secret, target_url=target_url)
        body_text = canonical_json(payload)
        body_bytes = body_text.encode("utf-8")
        # Defence in depth: GitHub digest must match these exact bytes.
        if provider == "github":
            _assert_github_body_matches(headers, secret, body_text)
        return {**headers, "Content-Type": "application/json"}, body_bytes

    if provider in FORM_PROVIDERS:
        headers = sign_payload(provider, payload, secret, target_url=target_url)
        body_bytes = _form_encode(payload)
        return {
            **headers,
            "Content-Type": "application/x-www-form-urlencoded",
        }, body_bytes

    raise ValueError(f"Unknown provider: {provider}")


def _form_encode(payload: dict[str, Any]) -> bytes:
    """Encode Twilio-style flat params as ``application/x-www-form-urlencoded``."""
    pairs: list[tuple[str, str]] = []
    for key, value in payload.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                pairs.append((key, "" if item is None else str(item)))
        else:
            pairs.append((key, "" if value is None else str(value)))
    return urlencode(pairs).encode("utf-8")


def _assert_github_body_matches(
    headers: dict[str, str],
    secret: str,
    body_text: str,
) -> None:
    from utils.signing import hmac_sha256_hex

    header = headers.get("X-Hub-Signature-256", "")
    expected = header.removeprefix("sha256=")
    actual = hmac_sha256_hex(secret, body_text)
    if expected != actual:
        raise RuntimeError(
            "Internal error: GitHub signature does not match outbound body bytes"
        )
