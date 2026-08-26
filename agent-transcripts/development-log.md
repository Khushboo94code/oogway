# Development log (agent-directed build)

A record of how the build was directed and the concrete failed attempts + corrections along the way.

## Phase 0 — Research (before writing code)
Directed three parallel research agents to verify, not assume:
- **Data source** → chose `ChatPRD/lennys-podcast-transcripts` (303 episodes, Markdown + YAML
  frontmatter with `title/guest/youtube_url/publish_date`) as the richest, citable, ready-to-ingest
  set. Noted the missing license → internal/educational use only.
- **Ship 30 for 30** → extracted the real frameworks (6 hook openers, 1/3/1 rhythm, Golden
  Intersection, headline 5-elements, skimmability) from primary sources, and flagged that the brief's
  "~1,250 words" is long-form, not a 250-word atomic essay → adapted the principles to long-form.
- **Claude Agent SDK + Ollama** → key finding: the Agent SDK drives the Claude Code CLI and is
  **Claude-model-centric — it cannot natively talk to Ollama/OpenAI**. The documented bridge is a
  LiteLLM proxy exposing an Anthropic `/v1/messages` endpoint. This shaped the whole provider design.

## Phase 1 — Requirements pivots (from user answers)
- **"I have an OpenAI key" (not Anthropic).** The assignment allows OpenAI as the cloud provider, but
  the mandated Agent SDK needs Claude. **Fix:** route the Agent SDK entirely through the LiteLLM
  Anthropic-passthrough → OpenAI (cloud) / Ollama (local); this also unified cloud+local into one
  agent path. Documented as the headline technical trade-off.
- **"Can we use Django?"** conflicts with the mandated **FastAPI** backend. Surfaced the conflict,
  proposed FastAPI + Jinja/HTMX as the Python-first compromise; user ultimately chose a **React/Vite
  SPA**, which the plan adopted.

## Phase 2 — Backend
- **Vector adapter timing.** First considered `pgvector`'s psycopg adapter (`register_vector_async`),
  which requires the `vector` extension to exist *before* connection configuration — a chicken/egg on
  a fresh DB. **Fix:** dropped the adapter entirely and pass vectors as `::vector` literal casts;
  removed the extension-timing coupling.
- **Embedding space vs provider toggle.** Using OpenAI embeddings in cloud mode and Ollama in local
  mode would create two incompatible 768-vs-1536-dim indexes. **Decision:** fix embeddings to
  `nomic-embed-text` (Ollama) in both modes so the index is toggle-proof (Ollama runs in both modes).
- **Agent-SDK reliability.** Because the SDK↔proxy↔Ollama bridge can't be validated without the live
  stack, built the direct LiteLLM path first (guaranteed demo) and made the orchestrator **fall back**
  from the Agent SDK path to the direct path on any error before tokens are emitted.
- Verified each step with `python -m compileall` after every module (kept the backend importable
  throughout).

## Phase 3 — Docker / packaging
- **Skills copy path.** Dockerfile first had `COPY skills ./skills`, but the Claude Agent SDK
  discovers skills from `.claude/skills/<name>/SKILL.md`. **Fix:** moved skills under
  `backend/.claude/skills/…` and `COPY .claude ./.claude`.
- **Python 3.14 on host.** Pinned the project + container to **Python 3.12** (`requires-python`,
  `python:3.12-slim`) so LiteLLM/pydantic/agent-sdk resolve reliably.
- **`make test` in Docker.** Tests were excluded by `.dockerignore` and the image installed only prod
  deps. **Fix:** un-ignored `tests/`, `COPY tests`, and install `.[dev]` so pytest runs in-image.

## Phase 4 — Frontend (verified with a real build)
Ran `npm run build` (tsc + vite) and fixed real errors:
1. **TS6310** — `tsconfig.node.json` referenced project "may not disable emit" (composite projects
   must emit). **Fix:** removed `noEmit` from `tsconfig.node.json`.
2. **`import.meta.env` typing** — added `src/vite-env.d.ts` (`/// <reference types="vite/client" />`).
3. **`@types/dompurify` conflict** — DOMPurify v3 ships its own types; removed the `@types` package.
4. **TS2339 "Property … does not exist on type 'never'"** on the `useRef` read. An explicit
   annotation didn't help (const control-flow narrows to the initializer's type). **Fix:** a type
   assertion `metaRef.current as ChatMeta | null` forces the type. Build then produced `dist/`.

## Phase 5 — Tests
- 24 dependency-free unit tests (chunking, routing, sanitize, artifact-parse) run locally via `uvx`
  and pass. DB/API/persistence tests use the real DB in Docker and **auto-skip** when Postgres is
  unreachable, so the suite never hard-fails in a bare environment.

## Phase 6 — Docs
Wrote README, PRD (with the discovery brief), design.md, architecture.md, and this log; mapped every
required deliverable to a file.

## Verification status at handoff
- Backend: `compileall` clean across the whole package.
- Frontend: `npm run build` clean (297 modules → `dist/`).
- Tests: 24/24 unit tests green; DB-backed tests ready for `make test`.
- End-to-end run (Docker up + ingest + live model) is the client's `make up` / `make ingest` step —
  the environment here had no Docker/keys — see the demo script and README run instructions.
