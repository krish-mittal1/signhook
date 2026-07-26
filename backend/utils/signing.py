"""Shared crypto and body-serialization helpers for webhook signatures.

Canonical JSON must match exactly between sign and send (and the verify harness),
or HMAC checks will fail for the same reason real Stripe integrations fail when
middleware re-serializes the body.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Union


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize payload the way we will put it on the wire for HMAC.

    Stripe (and GitHub) sign the raw request body. We use compact JSON with
    no ASCII escaping so the bytes are stable and UTF-8 friendly.
    """
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def hmac_sha256_hex(secret: str, message: Union[str, bytes]) -> str:
    key = secret.encode("utf-8")
    data = message if isinstance(message, bytes) else message.encode("utf-8")
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def hmac_sha1_base64(secret: str, message: Union[str, bytes]) -> str:
    """Twilio-style Base64(HMAC-SHA1(...)), stripped like the official SDK."""
    key = secret.encode("utf-8")
    data = message if isinstance(message, bytes) else message.encode("utf-8")
    digest = hmac.new(key, data, hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8").strip()
