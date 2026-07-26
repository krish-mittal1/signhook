"""Smoke-test containerized /api/send-webhook against the Compose echo service."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from providers import generate_payload  # noqa: E402

API = "http://127.0.0.1:8000"
# Echo is a Compose service; backend reaches it on the Docker network.
ECHO_BASE = "http://echo:9999"

CASES = [
    ("stripe", "payment_intent.succeeded", "whsec_smoke_stripe"),
    ("twilio", "message.received", "auth_smoke_twilio"),
    ("github", "push", "github_smoke_secret"),
]


def main() -> int:
    # UI reachable?
    ui = httpx.get("http://127.0.0.1:3000", timeout=10.0)
    print(f"UI GET / -> {ui.status_code} (len={len(ui.text)})")
    if ui.status_code != 200 or "signhook" not in ui.text.lower():
        print("FAIL: frontend container did not serve signhook UI", file=sys.stderr)
        return 1

    health = httpx.get(f"{API}/health", timeout=5.0)
    print(f"API /health -> {health.status_code} {health.text}")

    providers = httpx.get(f"{API}/api/providers", timeout=5.0)
    print(f"API /api/providers -> {providers.status_code}")

    for provider, event_type, secret in CASES:
        target = f"{ECHO_BASE}/hooks/{provider}"
        payload = generate_payload(provider, event_type)
        print("=" * 60)
        print(f"DOCKER UI-path send: {provider}/{event_type}")
        print(f"target_url: {target}")
        resp = httpx.post(
            f"{API}/api/send-webhook",
            json={
                "provider": provider,
                "payload": payload,
                "secret": secret,
                "target_url": target,
            },
            timeout=20.0,
        )
        print(f"API status: {resp.status_code}")
        data = resp.json()
        print(json.dumps(data, indent=2))
        if resp.status_code != 200 or data.get("status_code") != 200:
            print("FAIL: bad HTTP status", file=sys.stderr)
            return 1
        echo = json.loads(data["response_body"])
        if not echo.get("signature_verified"):
            print("FAIL: signature not verified", file=sys.stderr)
            return 1
        print(f"PASS {provider}: signature_verified=true (via Docker backend)")

    print("=" * 60)
    print("All Dockerized sends passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
