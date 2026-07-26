"""Shared helpers for building realistic-looking fake webhook IDs/payloads.

Provider-specific schemas live in each provider module; keep only cross-cutting
utilities here so contributors do not hunt through dead mock templates.
"""

from __future__ import annotations

import secrets
import time


def unix_timestamp() -> int:
    return int(time.time())


def fake_id(prefix: str, *, nbytes: int = 12) -> str:
    """Stripe/GitHub-style opaque id: ``{prefix}_{hex}``."""
    return f"{prefix}_{secrets.token_hex(nbytes)}"
