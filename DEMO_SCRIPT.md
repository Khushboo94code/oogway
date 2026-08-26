# Demo script & submission checklist

## Fresh-clone run-through (do this before recording)
```bash
git clone <repo> && cd oogway
cp .env.example .env
docker compose up --build -d
docker compose logs -f ollama-pull      # wait for "Models ready."
docker compose run --rm api python -m app.rag.ingest   # loads ~50 episodes
open http://localhost:8080
```
Verify: header badge shows `Ollama · llama3.1:8b · db ok`; a PMF question streams a cited answer.

## 2–3 minute video (camera on, upload to YouTube)

**0:00–0:20 — Problem (you on camera).**
"PMs and growth folks want Lenny's playbooks on demand — grounded and cited — and want to turn them
into content, without touching prompts, models, or infra. This is the Lenny Growth Assistant."

**0:20–1:00 — Grounded chat + citations (local Ollama).**
Point at the badge: "running entirely locally on Ollama — llama3.1:8b." Ask
*"What did guests say about finding product-market fit?"* Show tokens streaming, the `[1]` citations,
and the source chips linking to episodes. Then an out-of-corpus question to show it **abstains**
instead of hallucinating.

**1:00–1:40 — Skills: essay + artifact.**
`/essay how to run great onboarding` → show the ~1,250-word Ship-30 essay opening in the viewer.
Then `/artifact a one-page HTML summary of B2B growth loops` → show it render in the panel; click
**🛡 Security** to show the sandbox permits/blocks and what was stripped.

**1:40–2:20 — The technical trade-off (pick this one).**
"The assignment mandates the **Claude Agent SDK**, but it's Claude-model-centric and can't talk to
Ollama — and I only had an OpenAI key. So I route the Agent SDK through a **LiteLLM proxy** that
speaks Anthropic's API and forwards to OpenAI or Ollama. It's the faithful way to satisfy both the
SDK mandate and the local-model requirement — and I added an automatic fallback to a direct path so
the demo never breaks." Optionally flip `LLM_PROVIDER=cloud` to show the badge switch with no code change.

**2:20–2:40 — Operability.**
Show `docker compose up` is the whole thing, `/health` per-dependency, and `make test`. "Another team
can clone, run, and extend this in minutes."

## Submission checklist
- [ ] Public GitHub repo pushed, **no secrets** (`.env` git-ignored; only `.env.example` committed).
- [ ] `README.md`, `PRD.md`, `design.md`, `architecture.md`, `TESTING.md`, `BUILD_PLAN.md` present.
- [ ] `agent-transcripts/` with the development log (failed attempts + fixes).
- [ ] `backend/tests/` present; `make test` passes with the stack up.
- [ ] Fresh clone → `docker compose up` → `make ingest` verified on a clean machine.
- [ ] Demo video (camera on, shows local Ollama + one trade-off) uploaded to YouTube; link in the form.
- [ ] Submission form completed: https://forms.gle/LgotDHNVxW1mbzNE7
