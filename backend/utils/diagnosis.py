"""Rule-based failure diagnosis for send-webhook responses.

Real pattern matching lands later; this stub keeps the API shape stable.
"""

from __future__ import annotations

from typing import Optional


def diagnose(
    *,
    provider: str,
    status_code: Optional[int],
    response_body: Optional[str],
    error: Optional[str] = None,
) -> Optional[str]:
    """Return a plain-English hint, or None when nothing useful to say."""
    if error:
        return "Is your server running / ngrok tunnel up?"
    if status_code is None:
        return None
    if 200 <= status_code < 300:
        return None
    if 400 <= status_code < 500:
        return (
            f"Target returned {status_code}. "
            f"Check your {provider} signature verification and webhook secret."
        )
    return f"Target returned {status_code}."
