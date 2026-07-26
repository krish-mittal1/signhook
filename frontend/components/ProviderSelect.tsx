"use client";

type Props = {
  providers: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
};

export function ProviderSelect({ providers, value, onChange, disabled }: Props) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-zinc-700">Provider</span>
      <select
        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50"
        value={value}
        disabled={disabled || providers.length === 0}
        onChange={(e) => onChange(e.target.value)}
      >
        {providers.length === 0 && <option value="">Loading…</option>}
        {providers.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}
