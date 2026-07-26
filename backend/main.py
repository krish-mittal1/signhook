"""signhook — FastAPI entrypoint."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from inbox import NOT_ARMED_MESSAGE, Delivery, body_preview, inbox, sha256_hex
from probe import run_probe
from providers import PROVIDER_META, generate_payload, sign_payload
from schemas import (
    GeneratePayloadRequest,
    GeneratePayloadResponse,
    InboxArmRequest,
    InboxArmResponse,
    InboxLatestResponse,
    InboxProbeRequest,
    InboxProbeResponse,
    ProviderInfo,
    ProvidersResponse,
    SendWebhookRequest,
    SendWebhookResponse,
    SignPayloadRequest,
    SignPayloadResponse,
)
from utils.diagnosis import diagnose
from utils.outbound import SEND_TIMEOUT_SECONDS, prepare_outbound
from utils.verify import form_params_from_raw, verify_github, verify_stripe, verify_twilio

app = FastAPI(
    title="signhook",
    description="Generate, sign, and send fake webhooks for local integration testing.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _public_api_base() -> str:
    import os

    return os.environ.get("SIGNHOOK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/providers", response_model=ProvidersResponse)
def list_providers() -> ProvidersResponse:
    return ProvidersResponse(
        providers=[ProviderInfo(**meta) for meta in PROVIDER_META],
    )


@app.post("/api/generate-payload", response_model=GeneratePayloadResponse)
def api_generate_payload(body: GeneratePayloadRequest) -> GeneratePayloadResponse:
    try:
        payload = generate_payload(body.provider, body.event_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratePayloadResponse(payload=payload)


@app.post("/api/sign-payload", response_model=SignPayloadResponse)
def api_sign_payload(body: SignPayloadRequest) -> SignPayloadResponse:
    if body.provider == "twilio" and not body.target_url:
        raise HTTPException(
            status_code=400,
            detail="target_url is required when signing Twilio payloads",
        )
    try:
        headers = sign_payload(
            body.provider,
            body.payload,
            body.secret,
            target_url=body.target_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SignPayloadResponse(headers=headers)


@app.post("/api/send-webhook", response_model=SendWebhookResponse)
def api_send_webhook(body: SendWebhookRequest) -> SendWebhookResponse:
    """Sign the payload and POST it to ``target_url`` with matching body bytes."""
    try:
        headers, body_bytes = prepare_outbound(
            body.provider,
            body.payload,
            body.secret,
            body.target_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None

    try:
        with httpx.Client(timeout=SEND_TIMEOUT_SECONDS) as client:
            response = client.post(
                body.target_url,
                content=body_bytes,
                headers=headers,
            )
        status_code = response.status_code
        response_body = response.text[:8_000]
    except httpx.TimeoutException as exc:
        error = f"timeout: {exc}"
    except httpx.ConnectError as exc:
        error = f"connect: {exc}"
    except httpx.RequestError as exc:
        error = f"request: {exc}"

    diagnosis = diagnose(
        provider=body.provider,
        status_code=status_code,
        response_body=response_body,
        error=error,
    )

    return SendWebhookResponse(
        status_code=status_code,
        response_body=response_body if error is None else None,
        headers_sent=headers,
        diagnosis=diagnosis,
    )


@app.post("/api/inbox/arm", response_model=InboxArmResponse)
def api_inbox_arm(body: InboxArmRequest) -> InboxArmResponse:
    try:
        inbox.arm(body.provider, body.secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InboxArmResponse(
        provider=body.provider,
        listen_url=f"{_public_api_base()}/hooks/{body.provider}",
    )


@app.post("/api/inbox/disarm")
def api_inbox_disarm(provider: str | None = None) -> dict[str, str]:
    if provider is not None and provider not in {"stripe", "twilio", "github"}:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    inbox.disarm(provider)
    return {"status": "ok"}


@app.get("/api/inbox/latest", response_model=InboxLatestResponse)
def api_inbox_latest(provider: str) -> InboxLatestResponse:
    if provider not in {"stripe", "twilio", "github"}:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    return InboxLatestResponse(
        provider=provider,  # type: ignore[arg-type]
        delivery=inbox.latest_as_dict(provider),
    )


@app.post("/api/inbox/probe", response_model=InboxProbeResponse)
def api_inbox_probe(body: InboxProbeRequest) -> InboxProbeResponse:
    if not body.secret:
        raise HTTPException(status_code=400, detail=NOT_ARMED_MESSAGE)
    try:
        cases = run_probe(body.provider, body.secret, body.event_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InboxProbeResponse(provider=body.provider, cases=cases)


@app.post("/hooks/{provider}")
async def receive_hook(provider: str, request: Request) -> JSONResponse:
    """Built-in inbox: verify a delivery using the armed secret.

    Critical: read genuinely raw bytes before any other body-consuming logic.
    """
    # --- highest-risk line: raw bytes first, nothing else before this ---
    raw = await request.body()

    if provider not in {"stripe", "twilio", "github"}:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        secret = inbox.require_secret(provider)
    except LookupError:
        raise HTTPException(status_code=400, detail=NOT_ARMED_MESSAGE) from None

    header_map = {k: v for k, v in request.headers.items()}
    request_url = str(request.url)

    if provider == "stripe":
        result = verify_stripe(raw, header_map, secret)
    elif provider == "github":
        result = verify_github(raw, header_map, secret)
    else:
        params = form_params_from_raw(raw)
        result = verify_twilio(request_url, params, header_map, secret)

    delivery = Delivery(
        provider=provider,
        verified=result.ok,
        detail=result.detail,
        body_bytes=len(raw),
        body_sha256=sha256_hex(raw),
        body_preview=body_preview(raw),
        headers={
            k: v
            for k, v in header_map.items()
            if k.lower()
            in {
                "content-type",
                "stripe-signature",
                "x-twilio-signature",
                "x-hub-signature-256",
            }
        },
        request_url=request_url,
        signed_over=result.signed_over,
    )
    inbox.record(delivery)

    return JSONResponse(
        {
            "ok": True,
            "provider": provider,
            "body_bytes": delivery.body_bytes,
            "body_sha256": delivery.body_sha256,
            "signature_verified": delivery.verified,
            "detail": delivery.detail,
            "signed_over": delivery.signed_over,
        }
    )
