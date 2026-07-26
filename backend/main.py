"""signhook — FastAPI entrypoint."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from providers import PROVIDER_META, generate_payload, sign_payload
from schemas import (
    GeneratePayloadRequest,
    GeneratePayloadResponse,
    ProviderInfo,
    ProvidersResponse,
    SendWebhookRequest,
    SendWebhookResponse,
    SignPayloadRequest,
    SignPayloadResponse,
)
from utils.diagnosis import diagnose
from utils.outbound import SEND_TIMEOUT_SECONDS, prepare_outbound

app = FastAPI(
    title="signhook",
    description="Generate, sign, and send fake webhooks for local integration testing.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        # Cap body so a huge target response cannot blow up our reply.
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
