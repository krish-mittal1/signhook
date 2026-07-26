"use client";

import { useState } from "react";
import type { SendResult } from "@/lib/api";

type Props = {
  result: SendResult | null;
};

export function ResultPanel({ result }: Props) {
  const [headersOpen, setHeadersOpen] = useState(false);

  if (!result) {
    return (
      <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-4 py-8 text-center text-sm text-zinc-500">
        Results will appear here after Sign &amp; Send.
      </div>
    );
  }

  const ok =
    result.status_code !== null &&
    result.status_code >= 200 &&
    result.status_code < 300;

  return (
    <div className="space-y-4 rounded-md border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <span
          className={`inline-flex h-3 w-3 rounded-full ${
            result.status_code === null
              ? "bg-amber-500"
              : ok
                ? "bg-emerald-500"
                : "bg-red-500"
          }`}
          aria-hidden
        />
        <div>
          <p className="text-sm font-medium text-zinc-900">
            Status{" "}
            {result.status_code === null ? "— (no response)" : result.status_code}
          </p>
          <p className="text-xs text-zinc-500">
            {result.status_code === null
              ? "Connection failed or timed out"
              : ok
                ? "Success"
                : "Non-success response"}
          </p>
        </div>
      </div>

      {result.diagnosis && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          <p className="mb-1 font-medium">Diagnosis</p>
          <p className="leading-relaxed">{result.diagnosis}</p>
        </div>
      )}

      <div>
        <p className="mb-1.5 text-sm font-medium text-zinc-700">Response body</p>
        <pre className="max-h-56 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs text-zinc-800 whitespace-pre-wrap break-words">
          {result.response_body ?? "(empty)"}
        </pre>
      </div>

      <div>
        <button
          type="button"
          className="text-sm font-medium text-zinc-700 underline-offset-2 hover:underline"
          onClick={() => setHeadersOpen((v) => !v)}
        >
          {headersOpen ? "Hide" : "Show"} headers sent
        </button>
        {headersOpen && (
          <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs text-zinc-800 whitespace-pre-wrap break-words">
            {JSON.stringify(result.headers_sent, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
