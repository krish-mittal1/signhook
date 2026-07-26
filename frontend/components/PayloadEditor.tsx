"use client";

type Props = {
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
};

export function PayloadEditor({ value, onChange, disabled }: Props) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-zinc-700">
        Payload{" "}
        <span className="font-normal text-zinc-500">(editable JSON)</span>
      </span>
      <textarea
        className="h-80 w-full resize-y rounded-md border border-zinc-300 bg-zinc-50 px-3 py-2 font-mono text-xs leading-relaxed text-zinc-900 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50"
        spellCheck={false}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
