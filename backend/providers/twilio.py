"""Twilio webhook provider.

Generates flat, form-encoded-style parameter dicts matching Twilio's webhook
POST bodies, and signs them with the official ``X-Twilio-Signature`` scheme.

Signing (from Twilio's ``RequestValidator.compute_signature``):

1. Start with the full request URL (exact URL Twilio POSTed to).
2. For each POST parameter name, sorted alphabetically (unique names):
   for each distinct value of that name, sorted:
   append ``name + value`` with **no** separators.
3. ``Base64(HMAC-SHA1(auth_token, that_string))``

Reference:
https://www.twilio.com/docs/usage/security#validating-requests
https://github.com/twilio/twilio-python/blob/main/twilio/request_validator.py
"""

from __future__ import annotations

import secrets
from typing import Any, Callable, Mapping

from utils.payload_templates import unix_timestamp
from utils.signing import hmac_sha1_base64

EVENT_TYPES = [
    "message.received",
    "call.completed",
]

# Synthetic AccountSid (Twilio format: AC + 32 hex).
_ACCOUNT_SID = "AC" + ("a1b2c3d4" * 4)


def _sid(prefix: str) -> str:
    """Build a Twilio-style 34-character SID: 2-char prefix + 32 hex."""
    return prefix + secrets.token_hex(16)


def generate_payload(event_type: str) -> dict[str, str]:
    """Return a flat Twilio webhook parameter dict for ``event_type``.

    All values are strings — matching real ``application/x-www-form-urlencoded``
    POST bodies Twilio sends.

    Raises:
        ValueError: if ``event_type`` is not in ``EVENT_TYPES``.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unsupported Twilio event_type {event_type!r}. "
            f"Expected one of: {', '.join(EVENT_TYPES)}"
        )
    return _PARAM_BUILDERS[event_type]()


def sign_payload(
    payload: dict[str, Any],
    secret: str,
    *,
    target_url: str | None = None,
) -> dict[str, str]:
    """Sign Twilio form params; return ``X-Twilio-Signature`` header.

    Raises:
        ValueError: if ``target_url`` or ``secret`` is missing/empty.
    """
    if not target_url:
        raise ValueError(
            "target_url is required for Twilio signing "
            "(signature is HMAC over the exact request URL + POST params)"
        )
    if not secret:
        raise ValueError("Twilio auth token (secret) must be non-empty")

    signature = compute_twilio_signature(target_url, payload, secret)
    return {"X-Twilio-Signature": signature}


def compute_twilio_signature(
    uri: str,
    params: Mapping[str, Any],
    auth_token: str,
) -> str:
    """Mirror Twilio SDK ``RequestValidator.compute_signature``.

    Kept public so the verify harness can re-derive the signature without
    going through ``sign_payload``.
    """
    signed = uri
    if params:
        for name in sorted(set(params)):
            for value in sorted(set(_param_values(params, name))):
                signed += name + value
    return hmac_sha1_base64(auth_token, signed)


def _param_values(params: Mapping[str, Any], name: str) -> list[str]:
    """Normalize MultiDict / list / scalar values to a list of strings.

    Matches Twilio SDK ``get_values`` fallback for a plain dict, and accepts
    list values for multi-value params.
    """
    raw = params[name]
    if isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        values = [raw]
    # Form posts are always strings; coerce so HMAC input is deterministic.
    return ["" if v is None else str(v) for v in values]


# ---------------------------------------------------------------------------
# Flat parameter builders (Twilio webhook POST fields)
# ---------------------------------------------------------------------------


def _message_received() -> dict[str, str]:
    message_sid = _sid("SM")
    return {
        "MessageSid": message_sid,
        "SmsSid": message_sid,
        "SmsMessageSid": message_sid,
        "AccountSid": _ACCOUNT_SID,
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "Hello from webhook-sandbox",
        "NumMedia": "0",
        "NumSegments": "1",
        "SmsStatus": "received",
        "ApiVersion": "2010-04-01",
        "FromCity": "SAN FRANCISCO",
        "FromState": "CA",
        "FromZip": "94105",
        "FromCountry": "US",
        "ToCity": "SAN FRANCISCO",
        "ToState": "CA",
        "ToZip": "94107",
        "ToCountry": "US",
    }


def _call_completed() -> dict[str, str]:
    return {
        "CallSid": _sid("CA"),
        "AccountSid": _ACCOUNT_SID,
        "From": "+15551234567",
        "To": "+15557654321",
        "CallStatus": "completed",
        "Direction": "inbound",
        "ApiVersion": "2010-04-01",
        "CallDuration": "42",
        "Duration": "42",
        "Timestamp": str(unix_timestamp()),
        "CallbackSource": "call-progress-events",
        "SequenceNumber": "0",
    }


_PARAM_BUILDERS: dict[str, Callable[[], dict[str, str]]] = {
    "message.received": _message_received,
    "call.completed": _call_completed,
}
