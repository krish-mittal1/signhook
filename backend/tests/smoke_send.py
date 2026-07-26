"""Smoke-test /api/send-webhook against the optional echo receiver.

Prefer `smoke_inbox.py` (built-in inbox). This still works with echo on :9999:

    python tests/echo_receiver.py
    uvicorn main:app --port 8000
    python tests/smoke_send.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from providers import generate_payload  # noqa: E402
from utils.outbound import prepare_outbound  # noqa: E402
from utils.signing import canonical_json  # noqa: E402

API = "http://127.0.0.1:8000"
ECHO = "http://127.0.0.1:9999"

CASES = [
    ("stripe", "payment_intent.succeeded", "whsec_smoke_stripe"),
    ("twilio", "message.received", "auth_smoke_twilio"),
    ("github", "push", "github_smoke_secret"),
]


def main() -> int:
    for provider, event_type, secret in CASES:
        target = f"{ECHO}/hooks/{provider}"
        payload = generate_payload(provider, event_type)
        headers, body_bytes = prepare_outbound(provider, payload, secret, target)

        print("=" * 60)
        print(f"CLIENT -> send {provider}/{event_type}")
        print(f"target_url: {target}")
        print(f"headers_sent: {json.dumps(headers, indent=2)}")
        print(f"body_bytes: {len(body_bytes)}")
        print(f"body_sha256: {hashlib.sha256(body_bytes).hexdigest()}")
        if provider in ("stripe", "github"):
            # Prove prepare_outbound body == canonical_json used for signing.
            assert body_bytes == canonical_json(payload).encode("utf-8")
            print("canonical_json bytes == outbound body: True")

        with httpx.Client(timeout=10.0) as client:
            api_resp = client.post(
                f"{API}/api/send-webhook",
                json={
                    "provider": provider,
                    "payload": payload,
                    "secret": secret,
                    "target_url": target,
                },
            )
        print(f"API status: {api_resp.status_code}")
        print(f"API response: {json.dumps(api_resp.json(), indent=2)}")
        data = api_resp.json()
        if data.get("status_code") != 200:
            print("FAIL: echo did not return 200", file=sys.stderr)
            return 1
        echo_body = json.loads(data["response_body"])
        if not echo_body.get("signature_verified"):
            print("FAIL: echo could not verify signature", file=sys.stderr)
            return 1
        if echo_body.get("body_sha256") != hashlib.sha256(body_bytes).hexdigest():
            print("FAIL: body sha256 mismatch client vs echo", file=sys.stderr)
            return 1
        print(f"PASS {provider}: signed bytes == sent bytes == verified")

    print("=" * 60)
    print("All smoke sends passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
