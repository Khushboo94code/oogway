# architecture.md

## 1. System overview

```
┌── web (nginx: React/Vite SPA) ──┐
│  chat · sessions · artifact view │
└───────────────┬──────────────────┘
        REST + SSE (/chat)
┌───────────────▼───────────────────────────── api (FastAPI) ─────────────────┐
│ routes: /health /sessions /chat /artifacts                                   │
│ middleware: request-id · CORS · structured error envelope                    │
│ ┌── agent layer ─────────────────────────────────────────────────────────┐  │
│ │ router (chat|essay|artifact)                                            │  │
│ │ orchestrator → SSE (start·token·meta·error·done), persists w/ citations │  │
│ │ backends: claude_sdk (Agent SDK)  ──fallback──▶  litellm (direct)        │  │
│ │ skills: ship-30 essay · artifact-gen (+ server sanitize)                 │  │
│ └───────────────┬───────────────────────────────┬────────────────────────┘  │
│  RAG: chunk·embed·retrieve                       │ model calls               │
│ ┌───────────────▼──────────┐          ┌──────────▼───────────┐               │
│ │ Postgres + pgvector       │          │ LiteLLM gateway (SDK) │               │
│ │ sessions·messages·chunks  │          └──────────┬───────────┘               │
│ └───────────────────────────┘                     │                          │
└────────────────────────────────────────────────── │ ─────────────────────────┘
   embeddings ▲ (nomic-embed-text)                   ▼
   ┌──────────┴─────────┐              LiteLLM proxy  (Anthropic /v1/messages passthrough)
   │ ollama (11434)     │◀── cloud→OpenAI / local→ollama ──┤ used by the Agent SDK backend
   └────────────────────┘
```

## 2. Component boundaries
- **Frontend** (`frontend/`): stateless SPA; talks only to the API over REST + SSE. Owns rendering
  and the client-side artifact isolation (iframe/CSP/DOMPurify).
- **API** (`backend/app`): request handling, validation, persistence, orchestration. No business
  logic in routes — they delegate to the agent layer / repository.
- **Agent layer** (`app/agent`): routing + orchestration + skills + backends. Provider-agnostic;
  the only place that knows about "chat vs essay vs artifact".
- **RAG** (`app/rag`): ingestion, chunking, embeddings, retrieval. Pure of provider concerns.
- **LLM gateway / proxy** (`app/llm`, `litellm/`): the only components that know a concrete model.
- **Data** (`app/db`, `app/repository`, `db/init.sql`): schema + typed data access.

## 3. Database schema (Postgres + pgvector)
```sql
sessions(id uuid pk, title text, user_metadata jsonb, created_at, updated_at)
messages(id uuid pk, session_id uuid fk→sessions on delete cascade,
         role text check(user|assistant|system), content text,
         provider text, model text, citations jsonb, artifact jsonb, created_at)
  index (session_id, created_at)
transcript_chunks(id uuid pk, episode_id text, episode_title text, guest text,
         source_url text, publish_date date, chunk_index int,
         chunk_text text, embedding vector(768))
  index hnsw (embedding vector_cosine_ops); index (episode_id)
```
Applied by `db/init.sql` (container init) **and** idempotently by `app.db.init_db()` at startup
(so native runs work too). Vectors are written/read as `::vector` literals — no adapter/extension
timing coupling.

## 4. API endpoints
| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | — | `{status, provider, model, agent_backend, checks:{db,ollama,litellm}}` |
| POST | `/sessions` | `{title?, user_metadata?}` | `SessionOut` (201) |
| GET | `/sessions` | — | `SessionOut[]` |
| GET | `/sessions/{id}` | — | `SessionOut` / 404 |
| GET | `/sessions/{id}/messages` | — | `MessageOut[]` |
| POST | `/chat` | `{session_id, message}` | **SSE**: `start`→`token*`→(`error`?)→`meta`→`done` |
| GET | `/artifacts/policy` | — | `{policy:{permits,blocks}}` |
| POST | `/artifacts/sanitize` | `{content}` | `{content, report:{removed,flagged,policy}}` |

Validation via Pydantic; errors return a uniform envelope
`{"error":{"type","message","request_id"}}`. SSE `meta` carries
`{citations, artifact, security_report, provider, model, grounded, intent, top_score}`.

## 5. Ingestion flow (`app/rag/ingest.py`)
`git clone ChatPRD/lennys-podcast-transcripts` → for each `episodes/*/transcript.md`:
parse YAML frontmatter (`title, guest, youtube_url, publish_date, …`) + body → **chunk**
(paragraph-aware, ~3.5k chars ≈ ~875 tokens, ~500 overlap) → **embed** each chunk with
`nomic-embed-text` (bounded concurrency) → **upsert** into `transcript_chunks` with full source
metadata. Idempotent: truncates + reloads on each run (a manual "refresh"); `INGEST_MAX_EPISODES`
caps the demo set. Traceability: every chunk carries `episode_id/title/guest/source_url` →
citations link straight back to the episode.

## 6. Retrieval flow (`app/rag/retrieve.py`)
Embed the query → `similarity_search` cosine top-k over the HNSW index →
`score = 1 - cosine_distance`. If `top_score < RETRIEVAL_MIN_SCORE` the answer is marked
**not grounded** (→ honest abstention). Build enumerated `[n]` context blocks for citation and a
de-duplicated citation list (best chunk per episode). Embedding failure (Ollama down) degrades
gracefully to "not grounded" with an `embeddings_unavailable` marker rather than erroring.

## 7. Agent routing & backends
**Router** (`app/agent/router.py`): deterministic keyword/slash rules → `chat | essay | artifact`
(fast, free, unit-tested). **Orchestrator** (`orchestrator.py`): persists the user turn, names the
session, retrieves context, dispatches by intent, streams SSE, and persists the assistant turn with
citations/artifact.

- **chat** → grounded streamed answer. Backend selection:
  - `AGENT_BACKEND=agent_sdk` → **Claude Agent SDK** (`backends/claude_sdk.py`): `ClaudeSDKClient`
    with an in-process MCP `retrieve_transcripts` tool; pointed at the LiteLLM proxy via
    `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/model `lenny-{cloud,local}`. On import failure or a
    runtime error **before** any token is emitted, the orchestrator falls back to the direct path.
  - `AGENT_BACKEND=litellm` → direct provider-agnostic streaming (`app/llm/gateway.py`).
- **essay** → Ship-30 skill prompt (`app/agent/skills.py`, mirrored in `.claude/skills/ship-30-essay`),
  streamed, saved as a Markdown artifact.
- **artifact** → skill returns `{type,title,content}`; HTML is server-sanitized; returned as an artifact.

## 8. Model toggle / provider abstraction
`LLM_PROVIDER` selects the model everywhere without code changes:
- **Direct path:** `gateway._resolve()` maps provider → `openai/<model>` or `ollama_chat/<model>`
  and calls `litellm.acompletion` (streaming). Fallback: cloud-without-key → local.
- **Agent-SDK path:** the LiteLLM **proxy** exposes an Anthropic `/v1/messages` endpoint; the SDK
  sends model `lenny-cloud`/`lenny-local`, which the proxy routes to OpenAI/Ollama
  (`litellm/config.yaml`). This is the only bridge that lets the Claude Agent SDK run on
  non-Anthropic models (documented "Claude Code with non-Anthropic models" pattern).
- **Embeddings** are fixed to `nomic-embed-text` (Ollama) in both modes, so the 768-dim index is
  provider-independent and never needs rebuilding on toggle.

## 9. Security
- **Generated HTML is untrusted.** Enforced boundary (client): `<iframe sandbox="">` (no scripts,
  no same-origin, no forms, no top-nav) + strict CSP
  (`default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none';
  form-action 'none'`) + **DOMPurify**. Defense-in-depth (server): `app/security/sanitize.py` strips
  `<script>`, `on*` handlers, `javascript:` URIs, nested iframes and **reports** what it removed;
  external refs are flagged (CSP blocks them). The viewer surfaces the permits/blocks policy.
- **Secrets:** only via env; `.env` git-ignored; `.env.example` has no secrets. LiteLLM proxy guarded
  by a master key. No secrets in prompts, logs, or the container image.
- **Grounding as a safety control:** the system prompt forbids outside knowledge; the score floor
  forces abstention — reducing confident-but-wrong output.

## 10. Observability & resilience
- Structured JSON logs with a per-request `request_id` spanning model/retrieval/db/artifact stages.
- `/health` probes db (+ chunk count), ollama, and litellm independently → `ok|degraded`.
- Graceful failure for: missing key (fallback), Ollama down (typed SSE `error` + degraded health +
  abstaining retrieval), model timeout (600s ceiling + typed error), empty retrieval (abstain),
  DB failure at startup (caught; app stays up so `/health` reports it).

## 11. Deployment topology
`docker compose` services: **db** (pgvector, healthcheck), **ollama** (+ one-shot **ollama-pull**),
**litellm** (proxy), **api** (FastAPI/uvicorn; depends on db-healthy + litellm), **web** (nginx-served
SPA; API URL inlined at build). Ports: web `8080`, api `8000`, db `5432`, ollama `11434`, litellm
`4000`. Volumes persist Postgres data and pulled Ollama models. One-command bring-up; ingestion is a
separate `docker compose run` step. Native dev path via `uv`/`npm` documented in the README.

## 12. Key trade-offs
- **pgvector reused as the vector store** (one datastore) vs a dedicated vector DB — simpler ops, one
  source of truth, fine at this scale.
- **Claude Agent SDK via proxy + automatic fallback** — faithful to the mandate *and* demo-safe,
  at the cost of a translation layer that needs live validation (documented risk).
- **RAG over long-context stuffing** — 300+ transcripts exceed context and cost; retrieval also gives
  precise, traceable citations.
- **Fixed embedding model** — couples both modes to Ollama for embeddings, in exchange for a stable,
  toggle-proof index.
