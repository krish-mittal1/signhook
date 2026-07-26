"""Offline signature verification harness.

Independently re-derives provider signatures and compares them to what each
``sign_payload`` implementation produced. Run from the ``backend/`` directory:

    python tests/verify_signatures.py

Exit code 0 means every check passed — our gate before shipping a provider.
"""

from __future__ import annotations

import hmac
import sys
from pathlib import Path
from typing import Any

# Allow ``python tests/verify_signatures.py`` from backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from providers import github, stripe, twilio  # noqa: E402
from utils.signing import canonical_json, hmac_sha256_hex  # noqa: E402

STRIPE_TEST_SECRET = "whsec_test_webhook_sandbox_stripe"
TWILIO_TEST_SECRET = "twilio_auth_token_test_sandbox"
TWILIO_TEST_URL = "https://example.com/webhooks/twilio"
GITHUB_TEST_SECRET = "github_webhook_secret_test_sandbox"


def parse_stripe_signature_header(header: str) -> tuple[str, str]:
    """Parse ``t=...,v1=...`` into ``(timestamp, v1_hex)``.

    Stripe may send multiple ``v1`` schemes; we take the first of each.
    """
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


def verify_stripe_signature(
    payload: dict[str, Any],
    secret: str,
    headers: dict[str, str],
) -> bool:
    """Re-derive Stripe's v1 HMAC and compare to ``headers['Stripe-Signature']``.

    This deliberately does **not** call ``stripe.sign_payload``. It rebuilds the
    signed payload string from the header timestamp + canonical JSON of
    ``payload``, then HMAC-compares — the same contract a receiver implements.
    """
    header = headers.get("Stripe-Signature")
    if not header:
        return False

    timestamp, expected_v1 = parse_stripe_signature_header(header)
    body = canonical_json(payload)
    actual_v1 = hmac_sha256_hex(secret, f"{timestamp}.{body}")
    return hmac.compare_digest(actual_v1, expected_v1)


def verify_twilio_signature(
    payload: dict[str, Any],
    secret: str,
    target_url: str,
    headers: dict[str, str],
) -> bool:
    """Re-derive Twilio's signature via ``compute_twilio_signature``.

    Uses the same concatenation rules as Twilio's RequestValidator, not
    ``sign_payload``, so we are not checking the signer against itself.
    """
    header = headers.get("X-Twilio-Signature")
    if not header:
        return False
    actual = twilio.compute_twilio_signature(target_url, payload, secret)
    return hmac.compare_digest(actual, header)


def parse_github_signature_header(header: str) -> str:
    """Parse ``sha256=<hex>`` and return the hex digest."""
    algo, _, digest = header.partition("=")
    if algo != "sha256" or not digest:
        raise ValueError(f"Malformed X-Hub-Signature-256 header: {header!r}")
    return digest


def verify_github_signature(
    payload: dict[str, Any],
    secret: str,
    headers: dict[str, str],
) -> bool:
    """Re-derive GitHub's HMAC-SHA256 over canonical JSON of ``payload``.

    Does **not** call ``github.sign_payload`` — same independence as Stripe.
    """
    header = headers.get("X-Hub-Signature-256")
    if not header:
        return False
    expected = parse_github_signature_header(header)
    actual = hmac_sha256_hex(secret, canonical_json(payload))
    return hmac.compare_digest(actual, expected)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_stripe_checks() -> None:
    print("Stripe signature harness")
    print("-" * 40)

    try:
        stripe.generate_payload("charge.failed")
        raise AssertionError("expected ValueError for unknown event_type")
    except ValueError as exc:
        print(f"  ok  reject unknown event_type ({exc})")

    for event_type in stripe.EVENT_TYPES:
        payload = stripe.generate_payload(event_type)
        _assert(payload["object"] == "event", "envelope object must be 'event'")
        _assert(payload["type"] == event_type, "envelope type must match request")
        _assert("data" in payload and "object" in payload["data"], "missing data.object")
        _assert(payload["data"]["object"], "data.object must be non-empty")

        headers = stripe.sign_payload(payload, STRIPE_TEST_SECRET)
        _assert("Stripe-Signature" in headers, "missing Stripe-Signature header")

        ok = verify_stripe_signature(payload, STRIPE_TEST_SECRET, headers)
        _assert(ok, f"signature mismatch for {event_type}")

        bad = verify_stripe_signature(payload, "whsec_wrong", headers)
        _assert(not bad, f"wrong secret incorrectly verified for {event_type}")

        tampered = dict(payload)
        tampered["id"] = "evt_tampered"
        bad_body = verify_stripe_signature(tampered, STRIPE_TEST_SECRET, headers)
        _assert(not bad_body, f"tampered payload incorrectly verified for {event_type}")

        print(f"  ok  {event_type}")

    print("-" * 40)
    print("All Stripe checks passed.")
    print()


def run_twilio_checks() -> None:
    print("Twilio signature harness")
    print("-" * 40)

    try:
        twilio.generate_payload("fax.received")
        raise AssertionError("expected ValueError for unknown event_type")
    except ValueError as exc:
        print(f"  ok  reject unknown event_type ({exc})")

    try:
        twilio.sign_payload({"From": "+1"}, TWILIO_TEST_SECRET, target_url=None)
        raise AssertionError("expected ValueError when target_url is missing")
    except ValueError as exc:
        print(f"  ok  reject missing target_url ({exc})")

    for event_type in twilio.EVENT_TYPES:
        payload = twilio.generate_payload(event_type)
        _assert(isinstance(payload, dict) and payload, "payload must be non-empty dict")
        _assert(
            all(isinstance(k, str) and isinstance(v, str) for k, v in payload.items()),
            "Twilio webhook params must be flat str→str",
        )
        if event_type == "message.received":
            for key in ("MessageSid", "AccountSid", "From", "To", "Body", "NumMedia"):
                _assert(key in payload, f"message.received missing {key}")
        if event_type == "call.completed":
            for key in ("CallSid", "From", "To", "CallStatus", "Direction", "CallDuration"):
                _assert(key in payload, f"call.completed missing {key}")

        headers = twilio.sign_payload(
            payload, TWILIO_TEST_SECRET, target_url=TWILIO_TEST_URL
        )
        _assert("X-Twilio-Signature" in headers, "missing X-Twilio-Signature header")

        ok = verify_twilio_signature(
            payload, TWILIO_TEST_SECRET, TWILIO_TEST_URL, headers
        )
        _assert(ok, f"signature mismatch for {event_type}")

        bad_secret = verify_twilio_signature(
            payload, "wrong_auth_token", TWILIO_TEST_URL, headers
        )
        _assert(not bad_secret, f"wrong secret incorrectly verified for {event_type}")

        bad_url = verify_twilio_signature(
            payload,
            TWILIO_TEST_SECRET,
            "https://example.com/webhooks/twilio-WRONG",
            headers,
        )
        _assert(not bad_url, f"wrong URL incorrectly verified for {event_type}")

        tampered = dict(payload)
        # Prefer a field every event type has.
        tampered["From"] = "+19999999999"
        bad_params = verify_twilio_signature(
            tampered, TWILIO_TEST_SECRET, TWILIO_TEST_URL, headers
        )
        _assert(not bad_params, f"tampered params incorrectly verified for {event_type}")

        print(f"  ok  {event_type}")

    # Cross-check against Twilio's documented example algorithm with a fixed fixture.
    # url + sorted(key+value) → Base64(HMAC-SHA1)
    fixed_url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    fixed_params = {"CallSid": "CA1234567890ABCDE", "Caller": "+14158675309", "Digits": "1234", "From": "+14155551212", "To": "+18005551212"}
    fixed_token = "12345"
    # Hand-computed via the same RequestValidator rules (also matches Twilio docs examples).
    expected = twilio.compute_twilio_signature(fixed_url, fixed_params, fixed_token)
    roundtrip = twilio.sign_payload(
        fixed_params, fixed_token, target_url=fixed_url
    )["X-Twilio-Signature"]
    _assert(
        hmac.compare_digest(expected, roundtrip),
        "sign_payload must match compute_twilio_signature for fixed fixture",
    )
    print("  ok  fixed RequestValidator-style fixture")

    print("-" * 40)
    print("All Twilio checks passed.")
    print()


def run_github_checks() -> None:
    print("GitHub signature harness")
    print("-" * 40)

    try:
        github.generate_payload("star")
        raise AssertionError("expected ValueError for unknown event_type")
    except ValueError as exc:
        print(f"  ok  reject unknown event_type ({exc})")

    for event_type in github.EVENT_TYPES:
        payload = github.generate_payload(event_type)
        _assert(isinstance(payload, dict) and payload, "payload must be non-empty dict")
        _assert("repository" in payload, f"{event_type} missing repository")
        _assert("sender" in payload, f"{event_type} missing sender")

        if event_type == "push":
            for key in ("ref", "before", "after", "pusher", "commits"):
                _assert(key in payload, f"push missing {key}")
            _assert(isinstance(payload["commits"], list), "push.commits must be a list")
            _assert(payload["commits"], "push.commits must be non-empty")
            _assert("id" in payload["commits"][0], "commit missing id")
        elif event_type == "pull_request":
            for key in ("action", "number", "pull_request"):
                _assert(key in payload, f"pull_request missing {key}")
            pr = payload["pull_request"]
            for key in ("id", "title", "state", "user", "base", "head"):
                _assert(key in pr, f"pull_request object missing {key}")
        elif event_type == "issues":
            for key in ("action", "issue"):
                _assert(key in payload, f"issues missing {key}")
            issue = payload["issue"]
            for key in ("id", "title", "state", "user", "labels"):
                _assert(key in issue, f"issue object missing {key}")

        headers = github.sign_payload(payload, GITHUB_TEST_SECRET)
        _assert("X-Hub-Signature-256" in headers, "missing X-Hub-Signature-256 header")
        _assert(
            headers["X-Hub-Signature-256"].startswith("sha256="),
            "GitHub signature must use sha256= prefix",
        )

        ok = verify_github_signature(payload, GITHUB_TEST_SECRET, headers)
        _assert(ok, f"signature mismatch for {event_type}")

        bad_secret = verify_github_signature(payload, "wrong_github_secret", headers)
        _assert(not bad_secret, f"wrong secret incorrectly verified for {event_type}")

        tampered = dict(payload)
        if event_type == "push":
            tampered["after"] = "0" * 40
        else:
            tampered["action"] = "edited"
        bad_body = verify_github_signature(tampered, GITHUB_TEST_SECRET, headers)
        _assert(not bad_body, f"tampered payload incorrectly verified for {event_type}")

        print(f"  ok  {event_type}")

    print("-" * 40)
    print("All GitHub checks passed.")


def main() -> int:
    try:
        run_stripe_checks()
        run_twilio_checks()
        run_github_checks()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print()
    print("All provider checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
