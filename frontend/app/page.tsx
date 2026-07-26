"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EventTypeSelect } from "@/components/EventTypeSelect";
import { PayloadEditor } from "@/components/PayloadEditor";
import { ProviderSelect } from "@/components/ProviderSelect";
import { ResultPanel } from "@/components/ResultPanel";
import {
  fetchProviders,
  generatePayload,
  sendWebhook,
  type ProviderId,
  type ProviderInfo,
  type SendResult,
} from "@/lib/api";

function pretty(payload: unknown) {
  return JSON.stringify(payload, null, 2);
}

const DEFAULT_TARGET_BASE =
  process.env.NEXT_PUBLIC_DEFAULT_TARGET_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:9999";

export default function HomePage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [provider, setProvider] = useState<ProviderId | "">("");
  const [eventType, setEventType] = useState("");
  const [targetUrl, setTargetUrl] = useState(
    `${DEFAULT_TARGET_BASE}/hooks/stripe`,
  );
  const [secret, setSecret] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [result, setResult] = useState<SendResult | null>(null);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => providers.find((p) => p.id === provider) ?? null,
    [providers, provider],
  );

  const eventTypes = selected?.event_types ?? [];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoadingProviders(true);
        const data = await fetchProviders();
        if (cancelled) return;
        setProviders(data.providers);
        if (data.providers.length > 0) {
          const first = data.providers[0];
          setProvider(first.id);
          setEventType(first.event_types[0] ?? "");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load providers — is the API running on :8000?",
          );
        }
      } finally {
        if (!cancelled) setLoadingProviders(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshPayload = useCallback(async (prov: ProviderId, et: string) => {
    if (!prov || !et) return;
    setGenerating(true);
    setError(null);
    try {
      const data = await generatePayload(prov, et);
      setPayloadText(pretty(data.payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate payload");
    } finally {
      setGenerating(false);
    }
  }, []);

  useEffect(() => {
    if (!provider || !eventType) return;
    void refreshPayload(provider, eventType);
  }, [provider, eventType, refreshPayload]);

  function onProviderChange(id: string) {
    const next = providers.find((p) => p.id === id);
    setProvider(id as ProviderId);
    setEventType(next?.event_types[0] ?? "");
    setResult(null);
    // Sensible default path for local echo receiver
    setTargetUrl(`${DEFAULT_TARGET_BASE}/hooks/${id}`);
  }

  function onEventTypeChange(et: string) {
    setEventType(et);
    setResult(null);
  }

  async function onSignAndSend() {
    if (!provider) return;
    setSending(true);
    setError(null);
    setResult(null);
    try {
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(payloadText) as Record<string, unknown>;
      } catch {
        throw new Error("Payload is not valid JSON — fix it before sending.");
      }
      if (!targetUrl.trim()) {
        throw new Error("target_url is required");
      }
      if (!secret.trim()) {
        throw new Error("secret is required");
      }
      const data = await sendWebhook({
        provider,
        payload,
        secret: secret.trim(),
        target_url: targetUrl.trim(),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <header className="mb-8 border-b border-zinc-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          signhook
        </h1>
        <p className="mt-1 text-sm text-zinc-600">
          Generate, sign, and send Stripe / Twilio / GitHub webhooks to your
          local server. Secrets never leave your machine.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <ProviderSelect
              providers={providers}
              value={provider}
              onChange={onProviderChange}
              disabled={loadingProviders}
            />
            <EventTypeSelect
              eventTypes={eventTypes}
              value={eventType}
              onChange={onEventTypeChange}
              disabled={loadingProviders || generating}
            />
          </div>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-zinc-700">Target URL</span>
            <input
              type="url"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              placeholder="https://xxxx.ngrok.io/webhooks/stripe"
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-zinc-700">
              Secret / auth token
            </span>
            <input
              type="password"
              autoComplete="off"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              placeholder="whsec_… / Twilio auth token / GitHub secret"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
          </label>

          <PayloadEditor
            value={payloadText}
            onChange={setPayloadText}
            disabled={generating}
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={sending || generating || !provider || !eventType}
              onClick={() => void onSignAndSend()}
            >
              {sending ? "Sending…" : "Sign & Send"}
            </button>
            <button
              type="button"
              className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
              disabled={generating || !provider || !eventType}
              onClick={() =>
                provider && eventType && void refreshPayload(provider, eventType)
              }
            >
              {generating ? "Generating…" : "Regenerate payload"}
            </button>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-medium text-zinc-700">Result</h2>
          <ResultPanel result={result} />
        </section>
      </div>
    </main>
  );
}
