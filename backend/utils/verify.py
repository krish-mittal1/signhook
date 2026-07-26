"""Independent webhook signature verifiers (receiver-side).

These re-derive HMACs the way a real integration should — they do **not** call
provider ``sign_payload`` helpers. Used by the built-in inbox and the offline
harness.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import parse_qs

from providers.twilio import compute_twilio_signature
from utils.signing import hmac_sha256_hex


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    detail: str
    signed_over: str | None = None


def parse_stripe_signature_header(header: str) -> tuple[str, str]:
    timestamp: str | None = None
    v1: str | None = None
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and timestamp is None:
            timestamp = value
        elif key == "v1" and v1 is None:
            v1 = value
    if timestamp is None or v1 is None:
        raise ValueError(f"Malformed Stripe-Signature header: {header!r}")
    return timestamp, v1


def verify_stripe(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
) -> VerifyResult:
    header = _header(headers, "stripe-signature", "Stripe-Signature")
    if not header:
        return VerifyResult(False, "missing Stripe-Signature")
    try:
        timestamp, expected_v1 = parse_stripe_signature_header(header)
    except ValueError as exc:
        return VerifyResult(False, str(exc))

    body_text = raw_body.decode("utf-8")
    signed_over = f"{timestamp}.{body_text}"
    actual = hmac_sha256_hex(secret, signed_over)
    if hmac.compare_digest(actual, expected_v1):
        return VerifyResult(
            True,
            f"raw-body HMAC match ({len(raw_body)} bytes)",
            signed_over=f"{timestamp}.<raw {len(raw_body)} bytes>",
        )
    return VerifyResult(
        False,
        f"HMAC mismatch over raw body ({len(raw_body)} bytes) — "
        "check secret or body re-serialization",
        signed_over=f"{timestamp}.<raw {len(raw_body)} bytes>",
    )


def verify_github(
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
) -> VerifyResult:
    header = _header(headers, "x-hub-signature-256", "X-Hub-Signature-256")
    if not header:
        return VerifyResult(False, "missing X-Hub-Signature-256")
    if not header.startswith("sha256="):
        return VerifyResult(False, "missing sha256= prefix on X-Hub-Signature-256")
    expected = header.removeprefix("sha256=")
    actual = hmac_sha256_hex(secret, raw_body)
    if hmac.compare_digest(actual, expected):
        return VerifyResult(True, f"raw-body HMAC match ({len(raw_body)} bytes)")
    return VerifyResult(
        False,
        f"HMAC mismatch over raw body ({len(raw_body)} bytes)",
    )


def verify_twilio(
    url: str,
    params: Mapping[str, Any],
    headers: Mapping[str, str],
    secret: str,
) -> VerifyResult:
    header = _header(headers, "x-twilio-signature", "X-Twilio-Signature")
    if not header:
        return VerifyResult(False, "missing X-Twilio-Signature")
    actual = compute_twilio_signature(url, params, secret)
    if hmac.compare_digest(actual, header):
        return VerifyResult(
            True,
            "URL+params HMAC match",
            signed_over=url,
        )
    return VerifyResult(
        False,
        f"HMAC mismatch (verified with url={url!r})",
        signed_over=url,
    )


def form_params_from_raw(raw_body: bytes) -> dict[str, Any]:
    """Parse ``application/x-www-form-urlencoded`` bytes into a flat param dict."""
    return {
        k: (vals[0] if len(vals) == 1 else vals)
        for k, vals in parse_qs(
            raw_body.decode("utf-8"), keep_blank_values=True
        ).items()
    }


def _header(headers: Mapping[str, str], *names: str) -> str:
    lower = {k.lower(): v for k, v in headers.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return ""
