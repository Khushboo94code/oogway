import type { Health } from "../types";

export default function ProviderBadge({ health }: { health: Health | null }) {
  if (!health) return <div className="text-xs text-slate-400">connecting…</div>;
  const local = health.provider === "local";
  const dbOk = health.checks?.db?.ok;
  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex items-center gap-1.5">
        <span
          className={`inline-block h-2 w-2 rounded-full ${local ? "bg-amber-500" : "bg-emerald-500"}`}
        />
        <span className="font-medium text-slate-700">{health.model}</span>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-slate-400">
        <span className="uppercase tracking-wide">{health.provider}</span>
        <span>· agent: {health.agent_backend}</span>
        <span className={dbOk ? "text-emerald-500" : "text-red-500"}>
          · db {dbOk ? "ok" : "down"}
        </span>
      </div>
    </div>
  );
}
