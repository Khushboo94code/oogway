# Testing

## Automated tests

| Suite | What it covers | Needs |
|---|---|---|
| `test_chunking.py` | Deterministic, paragraph-aware chunking; oversized-paragraph splitting | none |
| `test_router.py` | Intent routing (chat / essay / artifact), slash-command priority | none |
| `test_sanitize.py` | HTML sanitizer strips `<script>` / `on*` / `javascript:`, flags external refs | none |
| `test_artifact_parse.py` | Robust artifact JSON parsing (fences, prose, invalid, fallback) | none |
| `test_retrieve.py` | Grounding threshold + citation building (embeddings/search mocked) | light deps |
| `test_api.py` | `/health`, session CRUD, structured 404, **`/chat` SSE stream + persistence** (model mocked) | Postgres |
| `test_persistence.py` | Session-context isolation; citations + artifact persistence | Postgres |

Run everything in Docker (Postgres available, all deps installed):

```bash
make test            # docker compose run --rm api pytest -q
```

Run the dependency-free unit tests locally without Docker:

```bash
cd backend
uvx --with pytest-asyncio pytest tests/test_chunking.py tests/test_router.py \
    tests/test_sanitize.py tests/test_artifact_parse.py -q
```

DB-backed tests **skip automatically** when Postgres isn't reachable, so the suite
never hard-fails in a bare environment.

## Manual UI test plan (~5 minutes)

Prereqs: `docker compose up --build` is running and `make ingest` has completed.

1. **Health** — open `http://localhost:8080`. The header badge shows the provider
   (amber = local Ollama, green = cloud OpenAI), the model, and `db ok`.
2. **Grounded answer** — ask *"What did guests say about finding product-market fit?"*
   Expect: tokens stream in; the answer cites `[1]`/`[2]`; **Source chips** appear below
   the message linking to the episodes on YouTube.
3. **Follow-up context** — ask *"Summarize that in 3 bullets."* Expect it to build on the
   previous answer (session context preserved).
4. **"I don't know" behavior** — ask something clearly outside the corpus (e.g. *"What's the
   capital of Chad?"*). Expect the assistant to say the transcripts don't cover it, with no
   fabricated citation.
5. **Ship-30 essay** — send *"/essay how to run great user onboarding"*. Expect a ~1,250-word
   structured essay (hook, bold subheads, takeaway), and an **Open in viewer** button opening
   it in the artifact panel as Markdown.
6. **HTML artifact + sandbox** — send *"/artifact a one-page HTML summary of B2B growth loops"*.
   Expect the artifact panel to render styled HTML. Click **🛡 Security** to see what the
   sandbox permits/blocks and anything that was stripped.
7. **Sessions** — click **+ New chat**, confirm the previous conversation is preserved and
   selectable in the sidebar; each session keeps independent context.
8. **Provider toggle** — set `LLM_PROVIDER=cloud` (with `OPENAI_API_KEY`) in `.env`, restart,
   and confirm the badge flips to green/OpenAI with no code change.
9. **Resilience** — stop the `ollama` container and send a message; the app should surface a
   clear error rather than crashing, and `/health` should show `ollama` down.
