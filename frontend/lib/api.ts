export type ProviderId = "stripe" | "twilio" | "github";

export type ProviderInfo = {
  id: ProviderId;
  name: string;
  event_types: string[];
};

export type SendResult = {
  status_code: number | null;
  response_body: string | null;
  headers_sent: Record<string, string>;
  diagnosis: string | null;
};

export type InboxDelivery = {
  provider: string;
  verified: boolean;
  detail: string;
  body_bytes: number;
  body_sha256: string;
  body_preview: string;
  headers: Record<string, string>;
  request_url: string;
  signed_over: string | null;
  received_at: number;
};

export type ProbeCase = {
  id: string;
  expected: boolean;
  actual: boolean | null;
  passed: boolean;
  detail: string | null;
};

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function fetchProviders() {
  return request<{ providers: ProviderInfo[] }>("/api/providers");
}

export function generatePayload(provider: ProviderId, event_type: string) {
  return request<{ payload: Record<string, unknown> }>("/api/generate-payload", {
    method: "POST",
    body: JSON.stringify({ provider, event_type }),
  });
}

export function sendWebhook(body: {
  provider: ProviderId;
  payload: Record<string, unknown>;
  secret: string;
  target_url: string;
}) {
  return request<SendResult>("/api/send-webhook", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function armInbox(provider: ProviderId, secret: string) {
  return request<{ ok: boolean; provider: ProviderId; listen_url: string }>(
    "/api/inbox/arm",
    {
      method: "POST",
      body: JSON.stringify({ provider, secret }),
    },
  );
}

export function fetchInboxLatest(provider: ProviderId) {
  return request<{ provider: ProviderId; delivery: InboxDelivery | null }>(
    `/api/inbox/latest?provider=${encodeURIComponent(provider)}`,
  );
}

export function runInboxProbe(body: {
  provider: ProviderId;
  secret: string;
  event_type: string;
}) {
  return request<{ provider: ProviderId; cases: ProbeCase[] }>("/api/inbox/probe", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function inboxListenUrl(provider: ProviderId) {
  return `${API_URL}/hooks/${provider}`;
}
