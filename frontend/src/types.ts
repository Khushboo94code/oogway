export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  episode_title: string;
  guest?: string | null;
  source_url?: string | null;
  publish_date?: string | null;
  chunk_id?: string | null;
  score?: number | null;
}

export interface Artifact {
  type: "markdown" | "html";
  title: string;
  content: string;
}

export interface Message {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  artifact?: Artifact | null;
  provider?: string | null;
  model?: string | null;
}

export interface Health {
  status: "ok" | "degraded";
  provider: string;
  model: string;
  agent_backend: string;
  checks: Record<string, any>;
}

export interface ChatMeta {
  citations: Citation[];
  artifact: Artifact | null;
  security_report?: { removed: string[]; flagged: string[]; policy: any } | null;
  provider: string;
  model: string;
  grounded: boolean;
  intent: "chat" | "essay" | "artifact";
  top_score: number;
}

export interface ModelOption {
  id: string;
  provider: string;
  model: string;
  label: string;
  available: boolean;
}

export type SSEHandler = (event: string, data: any) => void;
