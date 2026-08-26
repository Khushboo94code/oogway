import { useEffect, useMemo, useState } from "react";
import DOMPurify from "dompurify";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { getPolicy } from "../api/client";
import type { Artifact, ChatMeta } from "../types";

// Enforced isolation for generated HTML: a locked-down iframe (sandbox="" => no
// scripts, no same-origin, no forms, no top-nav) + a strict CSP + DOMPurify.
const CSP =
  "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; form-action 'none'";

function buildSrcDoc(html: string): string {
  const clean = DOMPurify.sanitize(html, { ADD_TAGS: ["style"], ADD_ATTR: ["style"] });
  return `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${CSP}">
<style>body{font-family:ui-sans-serif,system-ui,sans-serif;margin:16px;color:#0f172a}</style>
</head><body>${clean}</body></html>`;
}

export default function ArtifactViewer({
  artifact,
  security,
  onClose,
}: {
  artifact: Artifact;
  security?: ChatMeta["security_report"];
  onClose: () => void;
}) {
  const [showPolicy, setShowPolicy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [policyFallback, setPolicyFallback] = useState<any>(null);
  const isHtml = artifact.type === "html";
  const srcDoc = useMemo(() => (isHtml ? buildSrcDoc(artifact.content) : ""), [artifact, isHtml]);

  useEffect(() => {
    if (!security?.policy) getPolicy().then((r) => setPolicyFallback(r.policy)).catch(() => {});
  }, [security]);

  const copy = async () => {
    await navigator.clipboard.writeText(artifact.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  const policy = security?.policy ?? policyFallback;

  return (
    <div className="flex h-full flex-col border-l border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-800">{artifact.title}</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-400">
            {isHtml ? "HTML · sandboxed" : "Markdown"}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowPolicy((s) => !s)}
            title="What the viewer permits/blocks"
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            🛡 Security
          </button>
          <button
            onClick={copy}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            onClick={onClose}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            ✕
          </button>
        </div>
      </div>

      {showPolicy && (
        <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
          <p className="mb-1 font-medium text-slate-700">
            Generated content is treated as untrusted. HTML renders in a sandboxed iframe
            (no scripts, no same-origin, no network) under a strict CSP.
          </p>
          {security?.removed && security.removed.length > 0 && (
            <p className="mb-1 text-red-600">Stripped: {security.removed.join(", ")}.</p>
          )}
          {policy && (
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div>
                <div className="font-medium text-emerald-600">Permits</div>
                <ul className="list-disc pl-4">
                  {policy.permits?.map((p: string, i: number) => <li key={i}>{p}</li>)}
                </ul>
              </div>
              <div>
                <div className="font-medium text-red-600">Blocks</div>
                <ul className="list-disc pl-4">
                  {policy.blocks?.map((b: string, i: number) => <li key={i}>{b}</li>)}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto">
        {isHtml ? (
          <iframe
            title={artifact.title}
            sandbox=""
            srcDoc={srcDoc}
            className="h-full w-full border-0 bg-white"
          />
        ) : (
          <div className="md p-5 text-sm text-slate-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
              {artifact.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
