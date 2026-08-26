# PRD — The Lenny Growth Assistant

## 1. Forward-deployment discovery brief

### User & problem
**Primary user:** a Product Manager or Growth practitioner on an internal product/growth team.
**Job to be done:** *"When I'm making a product or growth decision, I want the specific,
battle-tested playbooks from Lenny's Podcast on demand — and I want to turn the good ones into
publishable content — without reading 300 transcripts or fiddling with prompts, models, or infra."*
**Pain removed:** hours of manual transcript search; ungrounded ChatGPT answers they can't trust
or cite; and the blank-page cost of turning an insight into a written artifact.

### Success metrics (measurable)
1. **Grounding rate ≥ 90%** — share of substantive answers that include ≥ 1 valid transcript
   citation (or correctly abstain). *Instrumented via the `grounded` flag + citation count per
   answer.*
2. **Time-to-first-useful-answer < 10s** on the cloud provider (first streamed token).
3. **One-turn artifact** — an essay or artifact is produced in a single request in ≥ 95% of attempts.

### Assumptions (brief was incomplete)
- Lenny's transcripts are the **sole** knowledge source; no open-web answers.
- A single internal user context is enough (no auth/multi-tenant for v1); we still store
  `user_metadata` for future multi-user.
- The evaluator runs the demo on a laptop, so the local model must be small (`llama3.1:8b`).
- OpenAI is the available cloud provider (the assignment permits it); no Anthropic key is available.

### Scope
**Included (v1):** grounded streaming chat with citations + abstention; per-session persistence;
Ship-30 essay skill; artifact generation + sandboxed viewer; provider toggle (OpenAI/Ollama);
one-command Docker startup; health/observability; tests.
**Intentionally excluded (why):**
- **Auth / multi-tenant** — not needed to prove the product; deferred, schema-ready.
- **Automated transcript refresh (cron)** — ingestion is a documented, idempotent re-runnable
  script; live refresh is out of scope for a 1-day build.
- **Full 320-episode ingest for the demo** — we ingest a curated ~50-episode subset for speed;
  the code supports the full set (`INGEST_MAX_EPISODES=0`).
- **Per-token streaming polish on very slow local models** — graceful non-blocking fallback instead.

### Risks & trade-offs
| Risk | Mitigation |
|---|---|
| **Hallucination** | RAG grounding + a system prompt that forbids outside knowledge + a retrieval score floor that triggers honest abstention. |
| **Agent-SDK ↔ non-Anthropic-model bridge** (the top technical risk) | Route the Claude Agent SDK through a LiteLLM Anthropic-passthrough (a documented pattern) and **auto-fall-back** to the direct path on any failure. |
| **Local-model quality / latency** | Small model, streaming UX, cloud toggle for quality-sensitive use. |
| **Unsafe artifact HTML** | Treat as untrusted: sandboxed iframe (no scripts/same-origin/network) + strict CSP + DOMPurify + server-side strip; transparent "permits/blocks" panel. |
| **Data leakage / licensing** | Internal-only demo; transcripts not redistributed; no secrets committed; `.env` git-ignored. |
| **Cost** | `gpt-4o-mini` default, `gpt-4.1` opt-in; local mode is free. |

## 2. Personas
- **Priya (PM):** wants cited answers to "how did great teams do X" and a quick memo she can share.
- **Sam (Growth):** wants to turn a finding into a Ship-30 post and a one-pager for stakeholders.
- **Evaluator/Client engineer:** needs to clone, run, and trust the system in minutes, and extend it.

## 3. Core user flows
1. **Ask a grounded question** → router picks `chat` → retrieve top-k → stream a cited answer →
   sources shown as chips → follow-ups reuse session context.
2. **Write an essay** → `/essay <topic>` (or essay-intent phrasing) → grounded Ship-30 essay streams
   in → saved as a Markdown artifact openable in the viewer.
3. **Generate an artifact** → `/artifact <request>` → model returns `{type,title,content}` →
   HTML is sanitized → rendered in the sandboxed viewer with the security panel.
4. **Manage sessions** → New chat creates an isolated context; sidebar lists sessions by title.
5. **Switch provider** → change `LLM_PROVIDER`, restart → badge reflects the active model.

## 4. Functional requirements
- FR1 Sessions: create, list, fetch, list messages; independent context; persisted in Postgres.
- FR2 Chat: SSE streaming; grounded answers with inline `[n]` citations + source metadata; abstain
  when unsupported.
- FR3 Essay skill: encodes Ship-30 principles (not a one-off prompt); ~1,250 words; grounded.
- FR4 Artifact: Markdown or self-contained HTML; sandboxed rendering; server + client sanitization.
- FR5 Model config: provider switch via env; provider/model visible in UI; documented fallback.
- FR6 Knowledge base: documented ingest (load/chunk/index) traceable to source; retrieval with
  grounding threshold.
- FR7 Ops: `/health` per-dependency; structured logs w/ request-id; one-command startup; `.env.example`.

## 5. Acceptance criteria (samples)
- Asking a PMF question returns an answer with ≥ 1 citation whose `source_url` opens the episode.
- Asking an out-of-corpus question yields an explicit "not covered" with **no** fabricated citation.
- `/essay` returns a structured ~1,250-word essay with a hook, bold subheads, and a takeaway,
  openable in the viewer.
- `/artifact` HTML renders in the viewer; the Security panel lists what is permitted/blocked and
  any stripped constructs; `<script>` never executes.
- Two sessions do not leak messages into each other (covered by `test_persistence.py`).
- Stopping Ollama produces a clear error, not a crash; `/health` shows `ollama` down.

## 6. Non-functional
- Reproducible `docker compose up`; graceful handling of missing keys, unavailable Ollama, model
  timeouts, empty retrieval, and DB failures. Structured JSON logs. Clear request/response contracts
  with validation and a uniform error envelope.

## 7. Implementation plan
Scaffold + Compose + health → RAG ingest/retrieve → LiteLLM gateway + proxy → agent layer
(router, grounded chat, Agent SDK backend + fallback) → essay skill → artifact gen + sanitize →
React SPA (chat, sessions, citations, provider badge) → sandboxed artifact viewer → tests → docs →
fresh-clone run-through + demo. (See [`BUILD_PLAN.md`](BUILD_PLAN.md) for the hour-by-hour cut.)

## 8. Open questions / future work
Auth & multi-user; scheduled ingest refresh + episode-level freshness; timestamped deep-links into
YouTube; eval harness for grounding/faithfulness; caching; streaming the essay/artifact through the
Agent SDK path; reranking for retrieval quality.
