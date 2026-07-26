"""Tiny local echo receiver for manual send-webhook smoke tests.

Verifies that the raw body bytes match the signature header for each provider.
Run:

    python tests/echo_receiver.py
"""

from __future__ import annotations

import hashlib
import hmac
import sys
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from providers.twilio import compute_twilio_signature  # noqa: E402
from utils.signing import hmac_sha256_hex  # noqa: E402

# Must match the secrets the smoke client uses.
STRIPE_SECRET = "whsec_smoke_stripe"
TWILIO_SECRET = "auth_smoke_twilio"
GITHUB_SECRET = "github_smoke_secret"

app = FastAPI(title="signhook-echo")


def _preview(raw: bytes, limit: int = 180) -> str:
    text = raw.decode("utf-8", errors="replace")
    return text if len(text) <= limit else text[:limit] + "…"


@app.post("/hooks/{provider}")
async def echo(provider: str, request: Request) -> JSONResponse:
    raw = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    body_sha = hashlib.sha256(raw).hexdigest()

    print("=" * 60)
    print(f"ECHO received provider={provider}")
    print(f"URL: {request.url}")
    print(f"Content-Type: {headers.get('content-type')}")
    print(f"Body bytes: {len(raw)}")
    print(f"Body sha256: {body_sha}")
    print(f"Body preview: {_preview(raw)}")

    verified = False
    detail = ""

    if provider == "stripe":
        sig = headers.get("stripe-signature", "")
        print(f"Stripe-Signature: {sig}")
        verified, detail = _verify_stripe(raw, sig, STRIPE_SECRET)
    elif provider == "twilio":
        sig = headers.get("x-twilio-signature", "")
        print(f"X-Twilio-Signature: {sig}")
        url = str(request.url)
        flat_params = {
            k: (vals[0] if len(vals) == 1 else vals)
            for k, vals in parse_qs(
                raw.decode("utf-8"), keep_blank_values=True
            ).items()
        }
        verified, detail = _verify_twilio(url, flat_params, sig, TWILIO_SECRET)
        print(f"Parsed form keys: {sorted(flat_params)}")
    elif provider == "github":
        sig = headers.get("x-hub-signature-256", "")
        print(f"X-Hub-Signature-256: {sig}")
        verified, detail = _verify_github(raw, sig, GITHUB_SECRET)
    else:
        detail = f"unknown provider {provider}"

    print(f"Signature verified: {verified} ({detail})")
    print("=" * 60)

    return JSONResponse(
        {
            "ok": True,
            "provider": provider,
            "body_bytes": len(raw),
            "body_sha256": body_sha,
            "signature_verified": verified,
            "detail": detail,
        }
    )


def _verify_stripe(raw: bytes, header: str, secret: str) -> tuple[bool, str]:
    if not header:
        return False, "missing Stripe-Signature"
    timestamp = None
    v1 = None
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and timestamp is None:
            timestamp = value
        elif key == "v1" and v1 is None:
            v1 = value
    if timestamp is None or v1 is None:
        return False, "malformed Stripe-Signature"
    # Stripe signs the raw body string, not a re-parsed object.
    body_text = raw.decode("utf-8")
    actual = hmac_sha256_hex(secret, f"{timestamp}.{body_text}")
    ok = hmac.compare_digest(actual, v1)
    return ok, "raw-body HMAC match" if ok else "HMAC mismatch (body bytes ≠ signed bytes?)"


def _verify_github(raw: bytes, header: str, secret: str) -> tuple[bool, str]:
    if not header.startswith("sha256="):
        return False, "missing sha256= prefix"
    expected = header.removeprefix("sha256=")
    actual = hmac_sha256_hex(secret, raw)  # accept bytes
    ok = hmac.compare_digest(actual, expected)
    return ok, "raw-body HMAC match" if ok else "HMAC mismatch"


def _verify_twilio(url: str, params: dict, header: str, secret: str) -> tuple[bool, str]:
    if not header:
        return False, "missing X-Twilio-Signature"
    # Flatten list values the way RequestValidator does for multi-dicts.
    normalized: dict = {}
    for key, value in params.items():
        normalized[key] = value
    actual = compute_twilio_signature(url, normalized, secret)
    ok = hmac.compare_digest(actual, header)
    return ok, "URL+params HMAC match" if ok else f"HMAC mismatch (url={url!r})"


if __name__ == "__main__":
    print("Echo receiver on http://0.0.0.0:9999")
    uvicorn.run(app, host="0.0.0.0", port=9999, log_level="warning")
