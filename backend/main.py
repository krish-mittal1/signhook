"""Webhook Testing Sandbox — FastAPI entrypoint (Step 1: mock scaffold)."""

from __future__ import annotations

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

app = FastAPI(
    title="Webhook Testing Sandbox",
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
    """Mock send — does not HTTP POST yet (wired in a later step)."""
    try:
        headers = sign_payload(
            body.provider,
            body.payload,
            body.secret,
            target_url=body.target_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Placeholder response until real httpx send is implemented.
    status_code = 200
    response_body = '{"mock": true, "message": "send not implemented yet"}'
    diagnosis = diagnose(
        provider=body.provider,
        status_code=status_code,
        response_body=response_body,
    )
    return SendWebhookResponse(
        status_code=status_code,
        response_body=response_body,
        headers_sent=headers,
        diagnosis=diagnosis,
    )
