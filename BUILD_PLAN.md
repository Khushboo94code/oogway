# The Lenny Growth Assistant — Build Plan & Architecture

> FDE take-home. Target: ship a runnable, handoff-ready MVP **today** (2026-08-25),
> submit by tomorrow EOD. This doc is the north star; the 8 deliverables map back to it.

---

## 0. TL;DR — what we're building

A full-stack, AI chat app that answers product/growth questions **grounded in Lenny's
Podcast transcripts** (with citations), can turn an answer into a **Ship-30-style ~1,250-word
essay**, and can generate **Markdown/HTML artifacts rendered safely beside the chat** (Claude-Artifacts style).

Backend **FastAPI** + **Postgres (pgvector)** + **Claude Agent SDK** as the agent layer (routed via a
**LiteLLM proxy**), with a **config-driven model toggle** (cloud **OpenAI** ⇄ local **Ollama**) that
requires **no code changes**. One-command `docker compose up`. Local Ollama demo is mandatory and must work.

> **Decisions locked after discovery:** cloud provider = **OpenAI** (assignment permits it); no Anthropic key,
> so the Claude Agent SDK runs **entirely through a LiteLLM Anthropic-compatible proxy** → OpenAI (cloud) or
> Ollama (local) — a documented "Claude Code with non-Anthropic models" pattern. Frontend = **React + Vite +
> Tailwind SPA** talking to the FastAPI API (react-markdown + sandboxed `<iframe>` artifact viewer).

---

## 1. Scope decision (time-boxed to ~1 day)

### IN (MVP — must ship)
1. **Grounded RAG chat** over Lenny transcripts, streaming, with inline source citations + "I don't know" behavior.
2. **Sessions + persistence** in Postgres (independent context per session).
3. **Model toggle** cloud/local via env, visible in UI; graceful fallback.
4. **Ship-30 essay skill** (~1,250 words, structured, grounded).
5. **Artifact generation + in-app viewer** (Markdown + sandboxed HTML/CSS).
6. **One-command startup** (Docker Compose), `.env.example`, structured logs, health endpoint.
7. All 8 deliverables (repo, README, PRD, design.md, architecture.md, agent transcripts, tests, demo video).

### OUT (deliberately cut — documented in PRD "scope")
- Auth / multi-tenant users (single implicit user; store `user_metadata` field for future).
- Transcript auto-refresh cron (ingestion is a documented one-shot script; "refresh" is manual re-run).
- Full 303-episode ingest for the demo → ingest a **curated ~40–60 episode subset** (fast, still impressive); code supports the full set.
- Streaming token-level UI for the local model if Ollama is slow (fall back to non-streamed).
- Fancy eval harness; we ship meaningful unit/integration tests instead.

---

## 2. Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + Tailwind)                                   │
│  ┌────────────────────────┐   ┌───────────────────────────────────┐   │
│  │ Chat pane              │   │ Artifact Viewer (right pane)      │   │
│  │ - session list         │   │ - Markdown → react-markdown       │   │
│  │ - streaming messages   │   │ - HTML → sandboxed <iframe> +CSP  │   │
│  │ - citations chips      │   │ - "permits/blocks" explainer      │   │
│  │ - provider badge       │   │                                   │   │
│  └──────────┬─────────────┘   └───────────────────────────────────┘   │
└─────────────┼─────────────────────────────────────────────────────────┘
              │ REST + SSE (/chat stream)
┌─────────────▼─────────────────────────────────────────────────────────┐
│  Backend — FastAPI                                                     │
│  Routes: /health  /sessions  /sessions/{id}/messages  /chat  /artifacts│
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │ Agent layer — Claude Agent SDK (ClaudeSDKClient)              │    │
│  │  Router → picks skill/tool based on the request               │    │
│  │  Tools (in-process MCP):                                       │    │
│  │   • retrieve_transcripts(query)  → pgvector top-k + metadata   │    │
│  │   • write_ship30_essay(topic)    → essay skill                 │    │
│  │   • make_artifact(spec)          → md / html artifact          │    │
│  │  Skills (SKILL.md): ship-30-essay, artifact-gen               │    │
│  └───────────────┬───────────────────────────────────────────────┘    │
│                  │ all model calls go through ↓                        │
│  ┌───────────────▼───────────────────────────────────────────────┐    │
│  │ LiteLLM proxy (Anthropic /v1/messages passthrough)            │    │
│  │  Agent SDK always points ANTHROPIC_BASE_URL here.             │    │
│  │  LLM_PROVIDER = cloud → OpenAI (gpt-4.1 / gpt-4o-mini)         │    │
│  │  LLM_PROVIDER = local → Ollama (llama3.1:8b)                   │    │
│  │  Embeddings: nomic-embed-text (Ollama) — one space, both modes │    │
│  └───────────────────────────────────────────────────────────────┘    │
└──────────┬───────────────────────────────────┬────────────────────────┘
           │                                    │
   ┌───────▼────────┐                  ┌────────▼─────────┐
   │ Postgres +     │                  │ Ollama (sidecar) │
   │ pgvector       │                  │ llama3.1:8b      │
   │ sessions,      │                  │ nomic-embed-text │
   │ messages,      │                  └──────────────────┘
   │ chunks+embeds  │
   └────────────────┘
```

---

## 3. Key technical decisions & trade-offs

### 3.1 Data source → `ChatPRD/lennys-podcast-transcripts`
- 303 episodes, **Markdown + YAML frontmatter** (`title, guest, youtube_url, video_id, publish_date, …`) — perfect for citations.
- `git clone https://github.com/ChatPRD/lennys-podcast-transcripts` (~2.7 MB). Parse: split each `.md` on `---` for frontmatter vs body.
- Citation = guest + episode title + `youtube_url` (link back to the exact episode; can deep-link timestamps later).
- **License note (put in PRD/README):** no LICENSE file → all-rights-reserved; README says "educational/research use." Fine for an internal demo, not for redistribution/commercial. Document this as a risk.

### 3.2 Retrieval → Postgres + `pgvector` (one datastore for everything)
- Postgres is mandated for persistence → reuse it as the vector store via `pgvector`. Elegant: no extra infra.
- Pipeline: load `.md` → chunk (~800–1,000 tokens, ~150 overlap, split on headings/paragraphs) → embed → store `chunk_text`, `embedding`, and source metadata (episode id, title, guest, url, chunk index) → cosine `ivfflat` index.
- Query: embed question → top-k (k≈6) → pass chunks + metadata into the agent as grounded context. Every answer cites the chunks it used.
- **"I don't know" behavior:** if top-k similarity < threshold, or the model can't ground the claim, respond that the transcripts don't cover it (guardrail in the system prompt + a retrieval-confidence check).
- Trade-off vs long-context stuffing: 303 transcripts ≫ context window and expensive; RAG is the right call and satisfies "chunked, indexed, traced to source."

### 3.3 Provider abstraction → **LiteLLM proxy** (guarantees the Ollama demo + unifies the agent path)
- Single choke point for every model call, exposed as an **Anthropic-compatible `/v1/messages` endpoint** so the Claude Agent SDK can point `ANTHROPIC_BASE_URL` at it. `LLM_PROVIDER` + a model map in config = switch provider with **zero app-code changes** (the assignment's explicit requirement).
- `cloud` → OpenAI `gpt-4.1` (or `gpt-4o-mini` for cost) — assignment permits OpenAI as the cloud provider.
- `local` → `ollama_chat/llama3.1:8b` (mandatory demo).
- **Embeddings fixed to one model across both modes** → `nomic-embed-text` via Ollama (768-dim, free, local): keeps a single embedding space so the index is provider-independent. **Never mix embedding models on one index** (document this).
- Fallback behavior (document + implement): missing OpenAI key → auto-select local; Ollama unreachable → clear error + (if key present) fall back to cloud; proxy down → typed error surfaced to UI.

### 3.4 Agent layer → **Claude Agent SDK**, unified through the LiteLLM proxy
The mandate: build the agent layer with the Claude Agent SDK. The catch (from research): the
Agent SDK drives the Claude Code CLI and is **Claude-model-centric.** With **no Anthropic key**, we run it
against OpenAI/Ollama through the LiteLLM Anthropic-passthrough — a **documented pattern**
(`docs.litellm.ai/docs/tutorials/claude_non_anthropic_models`), which also collapses cloud + local into
**one agent code path**:

- **`ClaudeSDKClient`** hosts the agentic loop, sessions, and our custom tools (`retrieve_transcripts`, `write_ship30_essay`, `make_artifact`) exposed via **in-process MCP** (`@tool` + `create_sdk_mcp_server`), plus **SKILL.md** skills for the writing principles. `setting_sources=["project"]` + `allowed_tools` (gotcha: skills silently don't load without `setting_sources`).
- **Model toggle:** `ClaudeAgentOptions(env=...)` sets `ANTHROPIC_BASE_URL` → the LiteLLM proxy **always**; the proxy routes `cloud`→OpenAI or `local`→Ollama by `LLM_PROVIDER`. One env var switches everything.
- **This satisfies BOTH "use the Claude Agent SDK" AND "swap providers with no code change" via a single blessed path — the perfect technical trade-off to narrate in the demo video.**

**RISK + FALLBACK (decide early, ~timebox 60–90 min):** the whole agent layer now depends on the
Agent-SDK → LiteLLM-proxy translation (Anthropic tool_use/system-prompt semantics onto OpenAI/Ollama).
It's documented but still the top risk. If it's flaky under time pressure, fall back to:
> A thin `LLMProvider` interface + a small tool-calling agent loop built directly on the LiteLLM
> Python SDK (OpenAI-native for cloud, `ollama_chat/` for local), reusing the *exact same* skill prompts
> and retrieval tool. Provider swap stays config-only; we just don't run the Agent-SDK subprocess.

Keep essay/artifact/retrieval logic in **provider-agnostic modules** so either agent path imports them
unchanged — cheap insurance since skills/retrieval/DB are provider-independent regardless.

### 3.5 Ship-30 essay skill (encoded principles, not a one-off prompt)
Encode the real Ship-30 frameworks (from source research) into a `SKILL.md` + a structured tool:
- **Hook** = one of the 6 openers (declarative / question / controversial / moment-in-time / vulnerable / weird-insight); open a curiosity gap.
- **Headline** encodes WHO · WHAT · FEEL · PROMISE · HOW-MUCH.
- **Body** = stacked **1/3/1** blocks; each main point a **bold subhead** that tells the story on its own; apply the **Golden Intersection** (answer + narrative).
- **Skimmable**: short paragraphs, whitespace, bullets, selective bold; every sentence advances the point.
- **Length**: assignment asks ~1,250 words (long-form, not a 250-word atomic essay) → adapt principles to long-form: hook → 4–6 subhead sections → concrete takeaway/CTA.
- **Grounded**: essay claims must trace to retrieved transcript chunks; cite sources.

### 3.6 Artifact viewer security (they grade this explicitly)
Treat generated HTML as **untrusted**:
- **Markdown** → `react-markdown` + `rehype-sanitize` (no raw HTML injection).
- **HTML/CSS** → render in a **sandboxed `<iframe sandbox>`** (allow-scripts only if needed, but **not** `allow-same-origin` together with `allow-scripts`), served with a strict **CSP** (`default-src 'none'; style-src 'unsafe-inline'; img-src data:` …), plus **DOMPurify** sanitization before injecting via `srcdoc`. No network, no top-navigation, no access to parent DOM/cookies.
- The viewer shows a short **"what this permits / blocks and why"** panel — directly answers the rubric.

---

## 4. Repo structure

```
lenny-growth-assistant/
├── docker-compose.yml            # postgres(pgvector) + ollama + api + web
├── .env.example
├── README.md  PRD.md  design.md  architecture.md
├── agent-transcripts/            # coding-agent logs incl. failed attempts (secrets scrubbed)
├── data/                         # (gitignored) cloned transcripts
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py               # FastAPI app, routers, health, logging
│   │   ├── config.py             # env, LLM_PROVIDER, model map
│   │   ├── db.py                 # SQLAlchemy/psycopg + pgvector
│   │   ├── models.py             # sessions, messages, chunks
│   │   ├── schemas.py            # pydantic request/response contracts
│   │   ├── llm/gateway.py        # LiteLLM provider abstraction + fallback
│   │   ├── agent/
│   │   │   ├── client.py         # Claude Agent SDK ClaudeSDKClient wiring
│   │   │   ├── router.py         # chat vs essay vs artifact
│   │   │   └── tools.py          # @tool retrieve/essay/artifact (MCP)
│   │   ├── skills/
│   │   │   ├── ship-30-essay/SKILL.md
│   │   │   └── artifact-gen/SKILL.md
│   │   ├── rag/
│   │   │   ├── ingest.py         # clone→parse→chunk→embed→store
│   │   │   ├── chunk.py
│   │   │   └── retrieve.py
│   │   └── routes/               # chat, sessions, artifacts, health
│   └── tests/                    # pytest: api, retrieval, routing, persistence
└── frontend/
    ├── package.json  vite.config.ts  tailwind.config.js
    └── src/
        ├── App.tsx
        ├── api/client.ts         # REST + SSE
        ├── components/
        │   ├── ChatPane.tsx  SessionList.tsx  MessageBubble.tsx
        │   ├── CitationChips.tsx  ProviderBadge.tsx
        │   └── ArtifactViewer.tsx    # md + sandboxed html
        └── styles/
```

---

## 5. Data model (Postgres)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

sessions(
  id UUID PK, title TEXT, user_metadata JSONB,
  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)

messages(
  id UUID PK, session_id UUID FK, role TEXT,           -- user|assistant|system
  content TEXT, provider TEXT, model TEXT,
  citations JSONB,                                     -- [{episode,guest,url,chunk_id}]
  artifact JSONB,                                      -- {type:md|html, content}
  created_at TIMESTAMPTZ)

transcript_chunks(
  id UUID PK, episode_id TEXT, episode_title TEXT, guest TEXT,
  source_url TEXT, publish_date DATE, chunk_index INT,
  chunk_text TEXT, embedding VECTOR(768))              -- nomic-embed-text dim
CREATE INDEX ON transcript_chunks USING ivfflat (embedding vector_cosine_ops);
```

---

## 6. API contract (clear request/response, validation, structured errors)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + provider + db/ollama reachability |
| POST | `/sessions` | create session → `{id, title}` |
| GET | `/sessions` | list sessions |
| GET | `/sessions/{id}/messages` | full history |
| POST | `/chat` | `{session_id, message}` → **SSE stream** of tokens + final `{citations, artifact?}` |
| POST | `/artifacts/render` | validate/sanitize HTML server-side before viewer (optional hardening) |

- Pydantic validation, structured error envelope `{error:{type,message,request_id}}`, request-id logging.
- `/chat` streams; on provider error emits a typed error event; UI degrades gracefully.

---

## 7. Ingestion pipeline (`ingest.py`, documented one-shot)
1. `git clone` transcripts repo into `data/`.
2. For each `episodes/*/transcript.md`: parse YAML frontmatter + body.
3. Chunk body (~800–1k tokens, 150 overlap, heading/paragraph aware).
4. Embed each chunk (provider-fixed embedding model).
5. Upsert into `transcript_chunks` with full source metadata.
6. Log counts; idempotent re-run = "refresh". (Demo: curated 40–60 episode subset; full-set supported.)

---

## 8. Feature implementation notes
- **Grounded chat:** router → `retrieve_transcripts` tool → build grounded context → gateway model call (streamed) → attach citations. System prompt enforces grounding + "say when unsupported."
- **Ship-30 essay:** router detects essay intent (or explicit `/essay`) → `write_ship30_essay` uses the SKILL.md principles over retrieved context → returns essay as a **Markdown artifact** (renders in viewer).
- **Artifacts:** `make_artifact` returns `{type: md|html, content}`; frontend routes md → react-markdown, html → sandboxed iframe.

---

## 9. Deployment & ops
- `docker compose up` brings up: `db` (pgvector image), `ollama` (with model pull on first run), `api` (FastAPI/uvicorn), `web` (Vite build served static or dev).
- `.env.example`: `LLM_PROVIDER` (cloud|local), `OPENAI_API_KEY`, `OPENAI_MODEL`, `OLLAMA_URL`, `OLLAMA_MODEL`, `EMBED_MODEL`, `LITELLM_PROXY_URL`, `DATABASE_URL`. No secrets committed.
- **Resilience (implement + document):** missing key, Ollama down, model timeout, empty retrieval, DB connection failure — all handled with clear messages, not crashes.
- **Observability:** structured JSON logs with request-id spanning model/retrieval/db/artifact stages; `/health` surfaces each dependency.

---

## 10. Testing (deliverable #7)
- **API:** health, session create/list, chat happy-path (mocked model), validation/error envelopes.
- **Retrieval:** chunking determinism, top-k returns expected episode for a seeded query, threshold → "I don't know".
- **Routing:** chat vs essay vs artifact intent classification.
- **Persistence:** message saved with citations; session context isolation across two sessions.
- **Manual UI test plan** (short doc): new chat, ask grounded Q, follow-up, generate essay, generate HTML artifact, toggle provider, kill Ollama → graceful.

---

## 11. Hour-by-hour execution (aggressive 1-day)
| Block | Hours | Work |
|---|---|---|
| A | 0.0–1.0 | Repo skeleton, docker-compose (db+ollama), `.env.example`, health endpoint, pull Ollama model + `nomic-embed-text`. |
| B | 1.0–2.5 | Ingestion: clone → parse → chunk → embed → pgvector; verify retrieval on a seed query. |
| C | 2.5–3.5 | LLM gateway (LiteLLM) + provider toggle + fallbacks; smoke both providers. |
| D | 3.5–5.5 | Agent layer (Claude Agent SDK): tools + retrieval + grounded chat streaming end-to-end. **Timebox the Ollama-via-proxy bridge; fall back if needed.** |
| E | 5.5–6.5 | Ship-30 essay skill (SKILL.md + tool). |
| F | 6.5–7.5 | Frontend: chat pane, streaming, sessions, citations, provider badge. |
| G | 7.5–8.5 | Artifact viewer (md + sandboxed html) + security explainer. |
| H | 8.5–9.5 | Tests (api/retrieval/routing/persistence) + resilience paths. |
| I | 9.5–11 | Docs: README, PRD (+discovery brief), design.md, architecture.md, agent-transcripts folder. |
| J | 11–12 | End-to-end fresh-clone run-through; record 2–3 min demo (camera on, show Ollama). Submit. |

---

## 12. Deliverables checklist (maps to the 8 required)
- [ ] **1. Public GitHub repo** — structure above, no secrets.
- [ ] **2. README.md** — architecture, prereqs, install, env, cloud+local setup, run, tests, troubleshooting.
- [ ] **3. PRD.md** — discovery brief (user/problem, success metric, assumptions, scope, risks), flows, acceptance criteria, plan.
- [ ] **4. design.md** — UI/UX principles, IA, states, responsive, accessibility, decisions.
- [ ] **5. architecture.md** — schema, endpoints, component boundaries, ingest/retrieval flow, agent routing, model toggle, security, deployment topology.
- [ ] **6. agent-transcripts/** — coding-agent logs incl. failed attempts + fixes (scrubbed).
- [ ] **7. Tests** — automated (api/retrieval/routing/persistence) + manual UI test plan.
- [ ] **8. Demo video** — 2–3 min, camera on, show product + local Ollama + one trade-off (the Agent-SDK↔Ollama bridge). Upload to YouTube.

---

## 13. Discovery brief seed (for the PRD)
- **User:** a PM / growth marketer on the product team who wants Lenny's hard-won playbooks on demand.
- **Job-to-be-done:** get a trustworthy, cited answer to a product/growth question and turn it into publishable content — without touching prompts, models, or infra.
- **Success metric (pick 1–2):** % of answers with a valid transcript citation (grounding rate ≥ 90%); time-to-first-useful-answer < 10s on cloud; essay produced in one turn.
- **Assumptions:** transcripts are the sole knowledge source; single internal user; demo runs on a laptop-class local model.
- **Risks/trade-offs:** hallucination (mitigated by RAG + grounding guardrail), local-model quality vs latency, unsafe HTML (sandbox+CSP+DOMPurify), transcript licensing (internal-only), cost (gpt-4o-mini default, gpt-4.1 opt-in).

---

## 14. Top risks & mitigations
1. **Agent SDK ↔ Ollama bridge fragility** → timebox 60–90 min; provider-agnostic skills + LiteLLM-direct fallback.
2. **Local model too slow/weak for streaming demo** → small model (`llama3.1:8b`), non-streamed fallback, pre-warm.
3. **Embedding-space mismatch** → fix one embedding model per index; document; don't mix cloud/local embeddings on the same index.
4. **Time** → curated subset ingest; cut list is explicit; docs written in parallel from this plan.
5. **Fresh-clone reproducibility** → dedicate block J to a clean `docker compose up` from zero.
```
