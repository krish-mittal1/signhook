"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EventTypeSelect } from "@/components/EventTypeSelect";
import { InboxPanel } from "@/components/InboxPanel";
import { PayloadEditor } from "@/components/PayloadEditor";
import { ProviderSelect } from "@/components/ProviderSelect";
import { ResultPanel } from "@/components/ResultPanel";
import {
  API_URL,
  armInbox,
  fetchInboxLatest,
  fetchProviders,
  generatePayload,
  inboxListenUrl,
  runInboxProbe,
  sendWebhook,
  type InboxDelivery,
  type ProbeCase,
  type ProviderId,
  type ProviderInfo,
  type SendResult,
} from "@/lib/api";

function pretty(payload: unknown) {
  return JSON.stringify(payload, null, 2);
}

const DEFAULT_TARGET_BASE =
  process.env.NEXT_PUBLIC_DEFAULT_TARGET_BASE?.replace(/\/$/, "") || API_URL;

export default function HomePage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [provider, setProvider] = useState<ProviderId | "">("");
  const [eventType, setEventType] = useState("");
  const [targetUrl, setTargetUrl] = useState(`${DEFAULT_TARGET_BASE}/hooks/stripe`);
  const [secret, setSecret] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [result, setResult] = useState<SendResult | null>(null);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [armed, setArmed] = useState(false);
  const [delivery, setDelivery] = useState<InboxDelivery | null>(null);
  const [probeCases, setProbeCases] = useState<ProbeCase[] | null>(null);
  const [probing, setProbing] = useState(false);

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
          setTargetUrl(inboxListenUrl(first.id));
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

  // Poll inbox latest while a provider is selected
  useEffect(() => {
    if (!provider) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await fetchInboxLatest(provider);
        if (!cancelled) setDelivery(data.delivery);
      } catch {
        /* ignore poll errors */
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [provider]);

  function onProviderChange(id: string) {
    const next = providers.find((p) => p.id === id);
    setProvider(id as ProviderId);
    setEventType(next?.event_types[0] ?? "");
    setResult(null);
    setProbeCases(null);
    setArmed(false);
    setTargetUrl(inboxListenUrl(id as ProviderId));
  }

  function onEventTypeChange(et: string) {
    setEventType(et);
    setResult(null);
  }

  async function onUseInbox() {
    if (!provider) return;
    setError(null);
    try {
      if (!secret.trim()) {
        throw new Error("Enter a secret before arming the inbox.");
      }
      const data = await armInbox(provider, secret.trim());
      setTargetUrl(data.listen_url);
      setArmed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to arm inbox");
    }
  }

  async function onRunChecks() {
    if (!provider || !eventType) return;
    setProbing(true);
    setError(null);
    try {
      if (!secret.trim()) {
        throw new Error("Enter a secret before running signature checks.");
      }
      const data = await runInboxProbe({
        provider,
        secret: secret.trim(),
        event_type: eventType,
      });
      setArmed(true);
      setProbeCases(data.cases);
      setTargetUrl(inboxListenUrl(provider));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Probe failed");
    } finally {
      setProbing(false);
    }
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
      // Auto-arm when targeting the built-in inbox so /hooks does not 400.
      if (targetUrl.trim().includes(`/hooks/${provider}`)) {
        await armInbox(provider, secret.trim());
        setArmed(true);
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

      <div className="mb-8">
        <InboxPanel
          delivery={delivery}
          probeCases={probeCases}
          armed={armed}
          probing={probing}
          onUseInbox={() => void onUseInbox()}
          onRunChecks={() => void onRunChecks()}
          disabled={!provider || loadingProviders}
        />
      </div>

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
          <h2 className="mb-3 text-sm font-medium text-zinc-700">Send result</h2>
          <ResultPanel result={result} />
        </section>
      </div>
    </main>
  );
}
