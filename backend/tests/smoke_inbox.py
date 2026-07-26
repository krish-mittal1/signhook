"""Smoke: inbox received bytes == signed/sent bytes; probe via real /hooks HTTP.

Requires API on :8000:

    uvicorn main:app --host 127.0.0.1 --port 8000
    python tests/smoke_inbox.py
"""

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
NOT_ARMED = "Arm the inbox with a secret first"

CASES = [
    ("stripe", "payment_intent.succeeded", "whsec_smoke_stripe"),
    ("twilio", "message.received", "auth_smoke_twilio"),
    ("github", "push", "github_smoke_secret"),
]


def main() -> int:
    client = httpx.Client(timeout=15.0)

    # Clear any prior arm state (local in-memory inbox)
    client.post(f"{API}/api/inbox/disarm")

    # Unarmed hooks → same 400
    r = client.post(f"{API}/hooks/stripe", content=b"{}", headers={"Content-Type": "application/json"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == NOT_ARMED
    print("ok  unarmed /hooks -> 400")

    # Empty-secret probe -> same 400
    r = client.post(
        f"{API}/api/inbox/probe",
        json={"provider": "stripe", "secret": "", "event_type": "payment_intent.succeeded"},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == NOT_ARMED
    print("ok  empty-secret /api/inbox/probe -> 400")

    for provider, event_type, secret in CASES:
        listen = f"{API}/hooks/{provider}"
        payload = generate_payload(provider, event_type)
        headers, body = prepare_outbound(provider, payload, secret, listen)
        sent_sha = hashlib.sha256(body).hexdigest()

        arm = client.post(
            f"{API}/api/inbox/arm",
            json={"provider": provider, "secret": secret},
        )
        assert arm.status_code == 200, arm.text

        resp = client.post(listen, content=body, headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["body_sha256"] == sent_sha, (
            f"{provider}: received sha {data['body_sha256']} != sent {sent_sha}"
        )
        assert data["body_bytes"] == len(body)
        assert data["signature_verified"] is True, data
        print(f"ok  {provider}: sent bytes == inbox bytes == verified")

        latest = client.get(f"{API}/api/inbox/latest", params={"provider": provider})
        assert latest.status_code == 200
        delivery = latest.json()["delivery"]
        assert delivery["body_sha256"] == sent_sha
        assert delivery["verified"] is True

        probe = client.post(
            f"{API}/api/inbox/probe",
            json={
                "provider": provider,
                "secret": secret,
                "event_type": event_type,
            },
        )
        assert probe.status_code == 200, probe.text
        cases = probe.json()["cases"]
        for case in cases:
            assert case["passed"] is True, json.dumps(case, indent=2)
        print(f"ok  {provider}: probe checklist all passed ({len(cases)} cases)")

    print("All inbox smoke checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
