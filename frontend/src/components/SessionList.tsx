import type { Session } from "../types";

export default function SessionList({
  sessions,
  currentId,
  onSelect,
  onNew,
}: {
  sessions: Session[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <button
        onClick={onNew}
        className="mb-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
      >
        + New chat
      </button>
      <div className="min-h-0 flex-1 space-y-1 overflow-auto pr-1">
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm ${
              s.id === currentId
                ? "bg-brand-50 font-medium text-brand-700"
                : "text-slate-600 hover:bg-slate-100"
            }`}
            title={s.title}
          >
            {s.title || "Untitled"}
          </button>
        ))}
        {sessions.length === 0 && (
          <div className="px-3 py-2 text-xs text-slate-400">No chats yet.</div>
        )}
      </div>
    </div>
  );
}
