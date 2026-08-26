import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { Message } from "../types";
import CitationChips from "./CitationChips";

export default function MessageBubble({
  message,
  onOpenArtifact,
}: {
  message: Message;
  onOpenArtifact?: (m: Message) => void;
}) {
  const isUser = message.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm text-white">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm">
        <div className="md">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
            {message.content || "…"}
          </ReactMarkdown>
        </div>
        {message.artifact && onOpenArtifact && (
          <button
            onClick={() => onOpenArtifact(message)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
          >
            🗂 Open “{message.artifact.title}” in viewer →
          </button>
        )}
        <CitationChips citations={message.citations} />
      </div>
    </div>
  );
}
