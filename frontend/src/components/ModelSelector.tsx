import type { ModelOption } from "../types";

export default function ModelSelector({
  options,
  currentId,
  disabled,
  onChange,
}: {
  options: ModelOption[];
  currentId: string;
  disabled?: boolean;
  onChange: (id: string) => void;
}) {
  return (
    <select
      value={currentId}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      title="Switch model — applies to your next message (no restart)"
      className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-700 outline-none focus:border-brand-500 disabled:opacity-50"
    >
      {options.length === 0 && <option value="">loading…</option>}
      {options.map((o) => (
        <option key={o.id} value={o.id} disabled={!o.available}>
          {o.label}
          {o.available ? "" : " (no key)"}
        </option>
      ))}
    </select>
  );
}
