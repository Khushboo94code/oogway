---
name: artifact-gen
description: Generate a self-contained Markdown document or a complete, safe HTML/CSS snippet based on the current conversation, for rendering in the in-app Artifact Viewer. Use when the user asks for a document, table, checklist, one-pager, landing page, or visual artifact.
---

# Artifact Generation Skill (placeholder — full rules added in Block G)

Produce ONE artifact from the conversation:
- Markdown: clean, self-contained; headings, lists, tables.
- HTML: a single self-contained snippet. Inline CSS only. No <script>, no external
  resources (no remote scripts/styles/fonts/images), no network calls, no forms that
  submit off-site. The viewer renders HTML in a sandboxed iframe with a strict CSP.

Return a JSON object: {"type": "markdown"|"html", "title": "...", "content": "..."}.
