import type { Citation } from "../types";

export default function CitationChips({ citations }: { citations?: Citation[] }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      <span className="text-[11px] font-medium text-slate-400">Sources:</span>
      {citations.map((c, i) => {
        const label = `${c.guest ? c.guest + " — " : ""}${c.episode_title}`;
        const chip = (
          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 hover:border-brand-500 hover:text-brand-600">
            {label}
            {c.score != null && <span className="ml-1 opacity-50">· {c.score.toFixed(2)}</span>}
          </span>
        );
        return c.source_url ? (
          <a key={i} href={c.source_url} target="_blank" rel="noreferrer">
            {chip}
          </a>
        ) : (
          <span key={i}>{chip}</span>
        );
      })}
    </div>
  );
}
