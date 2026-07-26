"""Rule-based failure diagnosis for send-webhook responses.

Plain-English hints for the failure modes that burn people integrating
Stripe / Twilio / GitHub webhooks. No LLM — just pattern matching.
"""

from __future__ import annotations

from typing import Optional

_SIG_HINTS = (
    "signature",
    "invalid signature",
    "webhook secret",
    "verify",
    "unauthorized",
    "forbidden",
    "x-hub-signature",
    "stripe-signature",
    "twilio",
)


def diagnose(
    *,
    provider: str,
    status_code: Optional[int],
    response_body: Optional[str],
    error: Optional[str] = None,
) -> Optional[str]:
    """Return a plain-English hint, or None when nothing useful to say."""
    if error:
        lowered = error.lower()
        if "timeout" in lowered:
            return (
                "Request timed out reaching the target. "
                "Is your server running / ngrok tunnel up, and is the URL reachable?"
            )
        return (
            "Could not connect to target_url. "
            "Is your server running / ngrok tunnel up?"
        )

    if status_code is None:
        return None

    if 200 <= status_code < 300:
        return None

    body = (response_body or "").lower()
    looks_like_sig_failure = status_code in {400, 401, 403} or any(
        hint in body for hint in _SIG_HINTS
    )

    if looks_like_sig_failure or 400 <= status_code < 500:
        return _provider_hint(provider, status_code)

    if status_code >= 500:
        return (
            f"Target returned {status_code} (server error). "
            "Your endpoint may be crashing while handling the webhook — "
            "check its logs."
        )

    return f"Target returned {status_code}."


def _provider_hint(provider: str, status_code: int) -> str:
    common = (
        f"Target returned {status_code}. "
        "Also confirm the webhook secret/auth token is non-empty and matches "
        "what your server uses to verify."
    )

    if provider == "twilio":
        return (
            f"{common} "
            "Twilio: signature verification uses the exact request URL "
            "(including scheme, host, path, and query string) concatenated with "
            "sorted POST params. A mismatch vs the URL your validator rebuilds "
            "is the #1 real-world failure."
        )

    if provider == "stripe":
        return (
            f"{common} "
            "Stripe: verify against the raw request body bytes — do not "
            "json.loads + re-dump before HMAC. Any re-serialization "
            "(key order, spaces) breaks Stripe-Signature."
        )

    if provider == "github":
        return (
            f"{common} "
            "GitHub: the header must look like "
            "`X-Hub-Signature-256: sha256=<hex>` — compare the hex digest "
            "(with the `sha256=` prefix stripped) using a timing-safe compare."
        )

    return common
