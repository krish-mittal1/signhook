"""In-memory webhook inbox for local signature verification.

Single-user / single-process: one armed secret per provider, last few deliveries.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

NOT_ARMED_MESSAGE = "Arm the inbox with a secret first"

_MAX_DELIVERIES = 5


@dataclass
class Delivery:
    provider: str
    verified: bool
    detail: str
    body_bytes: int
    body_sha256: str
    body_preview: str
    headers: dict[str, str]
    request_url: str
    signed_over: str | None
    received_at: float = field(default_factory=time.time)


class Inbox:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._secrets: dict[str, str] = {}
        self._deliveries: dict[str, deque[Delivery]] = {}

    def arm(self, provider: str, secret: str) -> None:
        if not secret:
            raise ValueError(NOT_ARMED_MESSAGE)
        with self._lock:
            self._secrets[provider] = secret

    def disarm(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._secrets.clear()
            else:
                self._secrets.pop(provider, None)

    def is_armed(self, provider: str) -> bool:
        with self._lock:
            return bool(self._secrets.get(provider))

    def get_secret(self, provider: str) -> str | None:
        with self._lock:
            return self._secrets.get(provider)

    def require_secret(self, provider: str) -> str:
        secret = self.get_secret(provider)
        if not secret:
            raise LookupError(NOT_ARMED_MESSAGE)
        return secret

    def record(self, delivery: Delivery) -> None:
        with self._lock:
            bucket = self._deliveries.setdefault(
                delivery.provider, deque(maxlen=_MAX_DELIVERIES)
            )
            bucket.appendleft(delivery)

    def latest(self, provider: str) -> Delivery | None:
        with self._lock:
            bucket = self._deliveries.get(provider)
            if not bucket:
                return None
            return bucket[0]

    def latest_as_dict(self, provider: str) -> dict[str, Any] | None:
        item = self.latest(provider)
        return asdict(item) if item else None


inbox = Inbox()


def body_preview(raw: bytes, limit: int = 240) -> str:
    text = raw.decode("utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + "…"


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
