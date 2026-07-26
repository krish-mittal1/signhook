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

const API_URL =
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
