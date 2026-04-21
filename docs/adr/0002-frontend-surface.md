# ADR-0002 — Frontend surface for the reasoning canvas

- **Status:** Accepted (2026-04-20)
- **Context:** v2 brief §4.3 prefers a Grafana app plugin; alternative is standalone Next.js with Grafana-in-iframe.

## Decision
Ship the canvas as a **new page inside the existing `gopal-ollychat-app`
Grafana app plugin** — not as a standalone Next.js app. Route:
`/a/gopal-ollychat-app/canvas`.

For the MVP vertical slice, the orchestrator *also* serves a minimal
static HTML demo at `GET /api/v2/canvas` that speaks the same WebSocket
protocol. This unblocks end-to-end testing without a full React rebuild
and doubles as a debug / QA surface. It ships behind the same feature flag
and is never advertised to users.

## Alternatives considered
- **Standalone Next.js** — rejected. Reinvents auth (Grafana plugin inherits
  user session + SSO). Adds a deploy artefact. Forces an iframe-embed of
  Grafana for the canvas, which we'd rather avoid (postMessage drift).
- **Extend the floating vanilla-JS widget** — rejected. The widget is a
  single IIFE, no framework. A split-pane diff viewer + Monaco editor
  doesn't belong inside it; it would double the bundle and complicate
  the v1 surface that users already rely on.
- **Swap the widget for the new canvas** — rejected. v2 §6 mandates
  backward compat. The widget stays as the "quick chat" surface; the
  canvas is the "interactive authoring" surface. Two fit-for-purpose
  surfaces.

## Consequences
- `src/pages/CanvasPage.tsx` is new; shares auth + theme via `@grafana/runtime`.
- Plugin manifest (`src/plugin.json`) gains one new `type: "page"` include
  behind a `role: "Editor"` guard (no Viewers on a write surface).
- The vanilla-JS widget's bundled JS remains at `dist/o11ybot-widget.js`
  — unchanged.
- For the MVP, `orchestrator/static/canvas.html` is the proving ground:
  - Plain HTML + vanilla JS (mirrors the widget's zero-dep approach)
  - Connects to `ws://localhost:8000/api/v2/stream`
  - Left pane = chat + reasoning timeline
  - Right pane = live Grafana iframe (bundled Grafana at :3002)

## Backward-compat
Widget keeps its exact current behaviour. The React plugin gains one
page, gated by role + feature flag.
