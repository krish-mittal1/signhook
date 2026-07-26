"""Optional standalone echo — prefers shared utils.verify when imported as a package.

Prefer the built-in inbox on the main API: POST /hooks/{provider} after arming.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from utils.verify import (  # noqa: E402
    form_params_from_raw,
    verify_github,
    verify_stripe,
    verify_twilio,
)

STRIPE_SECRET = "whsec_smoke_stripe"
TWILIO_SECRET = "auth_smoke_twilio"
GITHUB_SECRET = "github_smoke_secret"

app = FastAPI(title="signhook-echo")


@app.post("/hooks/{provider}")
async def echo(provider: str, request: Request) -> JSONResponse:
    raw = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    import hashlib

    body_sha = hashlib.sha256(raw).hexdigest()

    if provider == "stripe":
        result = verify_stripe(raw, headers, STRIPE_SECRET)
    elif provider == "twilio":
        result = verify_twilio(
            str(request.url), form_params_from_raw(raw), headers, TWILIO_SECRET
        )
    elif provider == "github":
        result = verify_github(raw, headers, GITHUB_SECRET)
    else:
        return JSONResponse({"ok": False, "detail": f"unknown provider {provider}"}, status_code=400)

    return JSONResponse(
        {
            "ok": True,
            "provider": provider,
            "body_bytes": len(raw),
            "body_sha256": body_sha,
            "signature_verified": result.ok,
            "detail": result.detail,
        }
    )


if __name__ == "__main__":
    print("Echo receiver on http://0.0.0.0:9999 (optional; prefer built-in inbox)")
    uvicorn.run(app, host="0.0.0.0", port=9999, log_level="warning")
