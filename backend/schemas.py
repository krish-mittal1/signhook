from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Provider = Literal["stripe", "twilio", "github"]


class GeneratePayloadRequest(BaseModel):
    provider: Provider
    event_type: str = Field(..., examples=["payment_intent.succeeded", "call.completed", "push"])


class GeneratePayloadResponse(BaseModel):
    payload: dict[str, Any]


class SignPayloadRequest(BaseModel):
    provider: Provider
    payload: dict[str, Any]
    secret: str
    target_url: Optional[str] = None  # required for Twilio signing


class SignPayloadResponse(BaseModel):
    headers: dict[str, str]


class SendWebhookRequest(BaseModel):
    provider: Provider
    payload: dict[str, Any]
    secret: str
    target_url: str


class SendWebhookResponse(BaseModel):
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    headers_sent: dict[str, str] = Field(default_factory=dict)
    diagnosis: Optional[str] = None


class ProviderInfo(BaseModel):
    id: Provider
    name: str
    event_types: list[str]


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]


class InboxArmRequest(BaseModel):
    provider: Provider
    secret: str


class InboxArmResponse(BaseModel):
    ok: bool = True
    provider: Provider
    listen_url: str


class InboxLatestResponse(BaseModel):
    provider: Provider
    delivery: Optional[dict[str, Any]] = None


class InboxProbeRequest(BaseModel):
    provider: Provider
    secret: str
    event_type: str


class InboxProbeCase(BaseModel):
    id: str
    expected: bool
    actual: Optional[bool] = None
    passed: bool
    detail: Optional[str] = None


class InboxProbeResponse(BaseModel):
    provider: Provider
    cases: list[InboxProbeCase]
