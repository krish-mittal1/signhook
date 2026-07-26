"""Built-in inbox probe: good/bad deliveries over the real /hooks HTTP path."""

from __future__ import annotations

import os
from typing import Any

import httpx

from inbox import NOT_ARMED_MESSAGE, inbox
from providers import generate_payload
from schemas import InboxProbeCase
from utils.outbound import prepare_outbound

HOOK_BASE = os.environ.get("SIGNHOOK_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def run_probe(provider: str, secret: str, event_type: str) -> list[InboxProbeCase]:
    if not secret:
        raise ValueError(NOT_ARMED_MESSAGE)

    inbox.arm(provider, secret)
    payload = generate_payload(provider, event_type)
    listen_url = f"{HOOK_BASE}/hooks/{provider}"

    cases: list[InboxProbeCase] = []

    # 1) Valid signature
    cases.append(_deliver_case(
        case_id="valid",
        provider=provider,
        payload=payload,
        secret=secret,
        target_url=listen_url,
        expected=True,
    ))

    # 2) Wrong secret used when signing (inbox still armed with correct secret)
    cases.append(_deliver_case(
        case_id="wrong_secret",
        provider=provider,
        payload=payload,
        secret="definitely_wrong_secret_for_probe",
        target_url=listen_url,
        expected=False,
    ))

    # 3) Tampered body after signing
    headers, body = prepare_outbound(provider, payload, secret, listen_url)
    tampered = body + b"x" if body else b"tampered"
    cases.append(_post_case(
        case_id="tampered_body",
        headers=headers,
        body=tampered,
        target_url=listen_url,
        expected=False,
    ))

    # 4) Twilio: sign with wrong URL
    if provider == "twilio":
        wrong_url = listen_url + "-WRONG"
        cases.append(_deliver_case(
            case_id="wrong_url",
            provider=provider,
            payload=payload,
            secret=secret,
            target_url=wrong_url,
            post_url=listen_url,
            expected=False,
        ))

    return cases


def _deliver_case(
    *,
    case_id: str,
    provider: str,
    payload: dict[str, Any],
    secret: str,
    target_url: str,
    expected: bool,
    post_url: str | None = None,
) -> InboxProbeCase:
    headers, body = prepare_outbound(provider, payload, secret, target_url)
    return _post_case(
        case_id=case_id,
        headers=headers,
        body=body,
        target_url=post_url or target_url,
        expected=expected,
    )


def _post_case(
    *,
    case_id: str,
    headers: dict[str, str],
    body: bytes,
    target_url: str,
    expected: bool,
) -> InboxProbeCase:
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(target_url, content=body, headers=headers)
    if resp.status_code == 400:
        detail = None
        try:
            detail = str(resp.json().get("detail"))
        except Exception:
            detail = resp.text
        return InboxProbeCase(
            id=case_id,
            expected=expected,
            actual=None,
            passed=False,
            detail=detail,
        )
    data = resp.json()
    actual = bool(data.get("signature_verified"))
    return InboxProbeCase(
        id=case_id,
        expected=expected,
        actual=actual,
        passed=actual is expected,
        detail=data.get("detail"),
    )
