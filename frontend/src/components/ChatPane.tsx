import { useEffect, useRef, useState } from "react";
import type { Message } from "../types";
import MessageBubble from "./MessageBubble";

const EXAMPLES = [
  "What did guests say about finding product-market fit?",
  "Write a Ship-30 essay on great activation onboarding",
  "Make an HTML one-pager summarizing B2B growth loops",
];

export default function ChatPane({
  messages,
  streaming,
  liveText,
  onSend,
  onOpenArtifact,
}: {
  messages: Message[];
  streaming: boolean;
  liveText: string;
  onSend: (text: string) => void;
  onOpenArtifact: (m: Message) => void;
}) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, liveText]);

  const submit = () => {
    const t = input.trim();
    if (!t || streaming) return;
    onSend(t);
    setInput("");
  };

  const empty = messages.length === 0 && !streaming;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-auto px-6 py-6">
        {empty && (
          <div className="mx-auto mt-10 max-w-lg text-center">
            <h2 className="text-lg font-semibold text-slate-700">The Lenny Growth Assistant</h2>
            <p className="mt-1 text-sm text-slate-500">
              Grounded answers from Lenny's Podcast — plus essays and rendered artifacts.
            </p>
            <div className="mt-5 flex flex-col gap-2">
              {EXAMPLES.map((e) => (
                <button
                  key={e}
                  onClick={() => onSend(e)}
                  className="rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-slate-600 hover:border-brand-300 hover:text-brand-700"
                >
                  {e}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={m.id ?? i} message={m} onOpenArtifact={onOpenArtifact} />
        ))}

        {streaming && (
          <MessageBubble
            message={{ role: "assistant", content: liveText || "…" }}
          />
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 bg-white px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask about product & growth…  (try /essay or /artifact)"
            className="max-h-40 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-brand-500"
          />
          <button
            onClick={submit}
            disabled={streaming || !input.trim()}
            className="rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40"
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
