import { useEffect, useRef, useState } from "react";
import {
  createSession,
  getHealth,
  getMessages,
  getModels,
  listSessions,
  setModel,
  streamChat,
} from "./api/client";
import ArtifactViewer from "./components/ArtifactViewer";
import ChatPane from "./components/ChatPane";
import ModelSelector from "./components/ModelSelector";
import ProviderBadge from "./components/ProviderBadge";
import SessionList from "./components/SessionList";
import type { Artifact, ChatMeta, Health, Message, ModelOption, Session } from "./types";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [security, setSecurity] = useState<ChatMeta["security_report"]>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [currentModelId, setCurrentModelId] = useState<string>("");

  const liveRef = useRef("");
  const metaRef = useRef<ChatMeta | null>(null);

  const refreshSessions = async () => {
    try {
      setSessions(await listSessions());
    } catch (e) {
      /* health badge will show db state */
    }
  };

  useEffect(() => {
    (async () => {
      try {
        setHealth(await getHealth());
      } catch {
        /* ignore */
      }
      getModels()
        .then((r) => {
          setModels(r.options);
          setCurrentModelId(r.current);
        })
        .catch(() => {});
      const ss = await listSessions().catch(() => [] as Session[]);
      setSessions(ss);
      if (ss.length > 0) setCurrentId(ss[0].id);
      else {
        const s = await createSession().catch(() => null);
        if (s) {
          setSessions([s]);
          setCurrentId(s.id);
        }
      }
    })();
  }, []);

  useEffect(() => {
    if (!currentId) return;
    setViewerOpen(false);
    setArtifact(null);
    getMessages(currentId).then(setMessages).catch(() => setMessages([]));
  }, [currentId]);

  const newChat = async () => {
    const s = await createSession();
    setSessions((prev) => [s, ...prev]);
    setCurrentId(s.id);
    setMessages([]);
  };

  const openArtifact = (m: Message) => {
    if (m.artifact) {
      setArtifact(m.artifact);
      setSecurity(null);
      setViewerOpen(true);
    }
  };

  const onModelChange = async (id: string) => {
    const opt = models.find((m) => m.id === id);
    if (!opt) return;
    setCurrentModelId(id);
    try {
      await setModel(opt.provider, opt.model);
    } catch (e) {
      setError(String(e));
    }
    getHealth().then(setHealth).catch(() => {});
    getModels()
      .then((r) => {
        setModels(r.options);
        setCurrentModelId(r.current);
      })
      .catch(() => {});
  };

  const send = async (text: string) => {
    if (!currentId || streaming) return;
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setStreaming(true);
    setLiveText("");
    liveRef.current = "";
    metaRef.current = null;

    try {
      await streamChat(currentId, text, (event, data) => {
        if (event === "token") {
          liveRef.current += data?.text ?? "";
          setLiveText(liveRef.current);
        } else if (event === "meta") {
          metaRef.current = data as ChatMeta;
        } else if (event === "error") {
          setError(data?.message ?? "Model error");
        }
      });
    } catch (e) {
      setError(String(e));
    }

    const meta = metaRef.current as ChatMeta | null;
    const assistant: Message = {
      role: "assistant",
      content: liveRef.current || (error ? `⚠️ ${error}` : "(no output)"),
      citations: meta?.citations,
      artifact: meta?.artifact ?? null,
      provider: meta?.provider,
      model: meta?.model,
    };
    setMessages((prev) => [...prev, assistant]);
    setStreaming(false);
    setLiveText("");

    if (meta) {
      setHealth((prev) => (prev ? { ...prev, provider: meta.provider, model: meta.model } : prev));
      if (meta.artifact) {
        setArtifact(meta.artifact);
        setSecurity(meta.security_report);
        setViewerOpen(true);
      }
    }
    refreshSessions();
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🎙️</span>
          <span className="font-semibold text-slate-800">Lenny Growth Assistant</span>
        </div>
        <div className="flex items-center gap-3">
          <ModelSelector
            options={models}
            currentId={currentModelId}
            disabled={streaming}
            onChange={onModelChange}
          />
          <ProviderBadge health={health} />
        </div>
      </header>

      {error && (
        <div className="bg-red-50 px-5 py-2 text-sm text-red-700">
          {error}{" "}
          <button className="underline" onClick={() => setError(null)}>
            dismiss
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 flex-col border-r border-slate-200 bg-slate-50 p-3 md:flex">
          <SessionList
            sessions={sessions}
            currentId={currentId}
            onSelect={setCurrentId}
            onNew={newChat}
          />
        </aside>

        <main className="flex min-h-0 flex-1 flex-col bg-slate-50">
          <ChatPane
            messages={messages}
            streaming={streaming}
            liveText={liveText}
            onSend={send}
            onOpenArtifact={openArtifact}
          />
        </main>

        {viewerOpen && artifact && (
          <section className="fixed inset-0 z-20 bg-white md:static md:z-auto md:w-[440px] lg:w-[520px]">
            <ArtifactViewer
              artifact={artifact}
              security={security}
              onClose={() => setViewerOpen(false)}
            />
          </section>
        )}
      </div>
    </div>
  );
}
