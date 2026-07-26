"""Smoke-test containerized inbox: arm → send → verified + byte match."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from providers import generate_payload  # noqa: E402
from utils.outbound import prepare_outbound  # noqa: E402

API = os.environ.get("SIGNHOOK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

CASES = [
    ("stripe", "payment_intent.succeeded", "whsec_smoke_stripe"),
    ("twilio", "message.received", "auth_smoke_twilio"),
    ("github", "push", "github_smoke_secret"),
]


def main() -> int:
    ui = httpx.get("http://127.0.0.1:3000", timeout=10.0)
    print(f"UI GET / -> {ui.status_code}")
    if ui.status_code != 200:
        print("FAIL: frontend not up", file=sys.stderr)
        return 1

    with httpx.Client(timeout=20.0) as client:
        client.post(f"{API}/api/inbox/disarm")
        for provider, event_type, secret in CASES:
            listen = f"{API}/hooks/{provider}"
            payload = generate_payload(provider, event_type)
            headers, body = prepare_outbound(provider, payload, secret, listen)
            sent_sha = hashlib.sha256(body).hexdigest()

            arm = client.post(
                f"{API}/api/inbox/arm", json={"provider": provider, "secret": secret}
            )
            assert arm.status_code == 200, arm.text

            # Path the UI uses: send-webhook API
            send = client.post(
                f"{API}/api/send-webhook",
                json={
                    "provider": provider,
                    "payload": payload,
                    "secret": secret,
                    "target_url": listen,
                },
            )
            assert send.status_code == 200, send.text
            send_data = send.json()
            assert send_data["status_code"] == 200, send_data
            echo = json.loads(send_data["response_body"])
            assert echo["signature_verified"] is True, echo
            assert echo["body_sha256"] == sent_sha, (
                f"{provider}: body sha mismatch sent={sent_sha} got={echo['body_sha256']}"
            )
            print(f"PASS {provider}: signed==sent==inbox verified")

            probe = client.post(
                f"{API}/api/inbox/probe",
                json={
                    "provider": provider,
                    "secret": secret,
                    "event_type": event_type,
                },
            )
            assert probe.status_code == 200, probe.text
            for case in probe.json()["cases"]:
                assert case["passed"] is True, case
            print(f"PASS {provider}: probe via real /hooks HTTP")

    print("All Dockerized inbox checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
