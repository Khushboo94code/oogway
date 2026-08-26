# design.md — UI/UX

## Principles
1. **Trust through grounding.** Every answer shows where it came from; citations are first-class
   (chips linking to the source episode), not footnotes. Abstention is a feature, shown plainly.
2. **Chat is the home; artifacts live beside it.** Like Claude Artifacts — the conversation stays
   put on the left while rendered output opens in a right-hand panel, never replacing the chat or
   dumping raw code.
3. **The system is legible.** The active provider/model, DB health, and the agent backend are
   always visible in the header badge. Streaming shows progress token-by-token.
4. **Low-friction, keyboard-first.** Enter to send, Shift+Enter for newline; example prompts on the
   empty state to teach capability (including `/essay` and `/artifact`).
5. **Safe by construction.** Untrusted generated HTML is visibly sandboxed, with a one-click
   explainer of what's permitted vs blocked.

## Information architecture
```
Header:  🎙 title ........................................ Provider badge (model · agent · db)
Sidebar: [+ New chat]  session list (titled by first message, newest first)
Main:    message stream (user right / assistant left, markdown) + streaming bubble
         composer (textarea + Send)
Panel:   Artifact viewer (opens on right; overlays full-screen on mobile)
```
Three zones map to the three jobs: **navigate** (sessions), **converse** (chat), **consume**
(artifact). Nothing competes for the same space.

## Key interaction states
- **Empty:** heading + subtitle + three example prompts (one per capability). Removes the blank-page problem.
- **Streaming:** live assistant bubble accumulates tokens; composer disabled; Send shows `…`.
- **Grounded answer:** inline `[n]` markers + a "Sources:" chip row (guest — episode, score, link).
- **Abstained:** plain "the transcripts don't cover this" with no chips.
- **Essay:** streams as markdown, then an **Open in viewer** button; artifact panel opens automatically.
- **Artifact (HTML):** panel shows rendered output in a sandboxed iframe; **🛡 Security** reveals the
  permits/blocks policy and anything stripped; **Copy** + **✕** actions.
- **Error:** a dismissible red banner (e.g. model/provider failure); the app stays usable; `/health`
  corroborates which dependency failed.
- **Provider fallback:** if cloud is selected without a key, the badge reflects the effective (local)
  model after the first turn.

## Responsive behavior
- **≥ md:** three columns (sidebar 256px · chat fluid · artifact 440–520px).
- **< md:** sidebar hides (chat gets full width); the artifact viewer becomes a full-screen overlay
  with a close button, so small screens still get the rendered output without a cramped split.
- Chat column is max-width-comfortable; message bubbles cap at ~80–85% width for readability.

## Accessibility
- Semantic landmarks (`header`, `aside`, `main`, `section`) and button elements for all actions.
- Color is never the only signal: the provider badge pairs the color dot with the text label and a
  `db ok/down` word; citations are text links, not color-coded chips alone.
- Keyboard: full composer control (Enter/Shift+Enter); focus-visible outlines via Tailwind defaults;
  links are real `<a>` with `rel="noreferrer"`.
- Streaming uses live text updates; the final message is persisted so screen-reader users can
  re-read the settled content.
- Contrast: slate-on-white body, brand-600 for primary actions (AA for text sizes used).

## Visual design decisions
- **Restraint over branding flourish** — this is an internal tool; a clean slate/indigo system reads
  as trustworthy and keeps attention on content and citations.
- **Markdown styled locally** (no heavy typography plugin) to keep the bundle small and predictable.
- **Iframe chrome minimal** — the artifact panel frames the output but doesn't decorate it, so the
  generated design speaks for itself.

## Trade-offs
- Chose a **React SPA** for a polished streaming chat + artifact split over a server-rendered
  template stack (faster, richer client interactions) — at the cost of a JS build step.
- Chose **auto-opening the artifact panel** on generation (discoverability) over keeping it manual
  (less surprise) — mitigated by an explicit close and an Open-in-viewer button on each message.
