"use client";

type Props = {
  eventTypes: string[];
  value: string;
  onChange: (eventType: string) => void;
  disabled?: boolean;
};

export function EventTypeSelect({
  eventTypes,
  value,
  onChange,
  disabled,
}: Props) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-zinc-700">Event type</span>
      <select
        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50"
        value={value}
        disabled={disabled || eventTypes.length === 0}
        onChange={(e) => onChange(e.target.value)}
      >
        {eventTypes.length === 0 && <option value="">No events</option>}
        {eventTypes.map((et) => (
          <option key={et} value={et}>
            {et}
          </option>
        ))}
      </select>
    </label>
  );
}
