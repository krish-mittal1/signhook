"use client";

import type { InboxDelivery, ProbeCase } from "@/lib/api";

type Props = {
  delivery: InboxDelivery | null;
  probeCases: ProbeCase[] | null;
  armed: boolean;
  probing: boolean;
  onUseInbox: () => void;
  onRunChecks: () => void;
  disabled?: boolean;
};

export function InboxPanel({
  delivery,
  probeCases,
  armed,
  probing,
  onUseInbox,
  onRunChecks,
  disabled,
}: Props) {
  return (
    <div className="space-y-4 rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium text-zinc-900">Built-in inbox</h2>
          <p className="text-xs text-zinc-500">
            Arm a secret, send here, and see live signature PASS/FAIL — no echo
            container needed.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
            disabled={disabled}
            onClick={onUseInbox}
          >
            Use inbox
          </button>
          <button
            type="button"
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50"
            disabled={disabled || probing}
            onClick={onRunChecks}
          >
            {probing ? "Running…" : "Run signature checks"}
          </button>
        </div>
      </div>

      <p className="text-xs text-zinc-600">
        Status:{" "}
        {armed ? (
          <span className="font-medium text-emerald-700">armed</span>
        ) : (
          <span className="font-medium text-amber-700">not armed</span>
        )}
      </p>

      {!delivery && (
        <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-3 py-6 text-center text-xs text-zinc-500">
          No deliveries yet. Click Use inbox, then Sign &amp; Send.
        </div>
      )}

      {delivery && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex h-2.5 w-2.5 rounded-full ${
                delivery.verified ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
            <span className="text-sm font-medium text-zinc-900">
              {delivery.verified ? "PASS" : "FAIL"}
            </span>
          </div>
          <p className="text-xs text-zinc-700">{delivery.detail}</p>
          <p className="font-mono text-[11px] text-zinc-500 break-all">
            sha256={delivery.body_sha256} ({delivery.body_bytes} bytes)
          </p>
          <pre className="max-h-40 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-2 font-mono text-[11px] text-zinc-800 whitespace-pre-wrap break-words">
            {delivery.body_preview}
          </pre>
        </div>
      )}

      {probeCases && probeCases.length > 0 && (
        <div className="space-y-2 border-t border-zinc-100 pt-3">
          <p className="text-xs font-medium text-zinc-700">Signature checks</p>
          <ul className="space-y-1.5">
            {probeCases.map((c) => (
              <li
                key={c.id}
                className="flex items-start gap-2 text-xs text-zinc-800"
              >
                <span
                  className={`mt-0.5 inline-flex h-2 w-2 shrink-0 rounded-full ${
                    c.passed ? "bg-emerald-500" : "bg-red-500"
                  }`}
                />
                <span>
                  <span className="font-medium">{c.id}</span>
                  {" — expected "}
                  {String(c.expected)}, got {String(c.actual)}
                  {c.detail ? ` (${c.detail})` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
