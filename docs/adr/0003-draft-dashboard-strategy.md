# ADR-0003 — Draft dashboard strategy

- **Status:** Accepted for MVP (2026-04-20)
- **Context:** v2 brief §4.4 — Grafana Live for a live-rendering right pane.
  Two options: ephemeral `[DRAFT]` dashboard + Grafana Live reload vs
  iframe + `postMessage`.

## Decision
**Option 1 — ephemeral draft dashboards** for MVP.

- When the reasoning engine plans a new dashboard, commit it as
  `title: "[DRAFT] <user title>"` with UID `ollybot-draft-<session_id>`
  into the dedicated folder `__ollybot_drafts__` (auto-created on first
  draft, tagged `ollybot-draft`).
- Each `panel_ready` reasoning event triggers a draft update via
  `POST /api/dashboards/db` with `overwrite: true`.
- The right pane reloads the draft iframe (Grafana's `dashboard/uid/<uid>`
  auto-refresh picks it up within one tick).
- On **apply**:
  - If the draft targets a **new** dashboard: deterministic UID derived
    from `hash(user_id + title + folder_uid)`. Clone the draft's `panels`
    + `templating` + `annotations` into a final dashboard at that UID;
    delete the draft; emit `action_committed` with the final URL.
  - If the draft targets an **edit** of an existing dashboard: copy the
    draft's `panels` into the target dashboard's current version with
    `overwrite: true, message: "Edited via OllyBot v2"`; append a Grafana
    annotation on the target dashboard history with the change summary +
    session id; delete the draft.
- On **discard / session timeout**: delete the draft + all snapshots.

## Alternatives considered
- **Option 2 — iframe + `postMessage`** — rejected for MVP. The contract
  with Grafana's panel-edit postMessage API isn't stable across LTS
  versions; relies on the user's Grafana version supporting the right
  message types.
- **Option 3 — build the panel JSON in-memory and render offline
  using Grafana's SSR render API** — rejected. The renderer is
  image-only; users can't interact (time-picker, hover, drill-down) with
  a rendered PNG.

## Consequences
- The `__ollybot_drafts__` folder is part of the deployed Grafana's state.
  A cleanup sweep (cron / background task) deletes any draft dashboard
  whose session TTL has expired.
- Grafana's audit log gets `[DRAFT]`-noise during authoring; filter by
  the `ollybot-draft` tag when reporting.
- The deterministic final-UID scheme means re-running a create flow
  with the same `(user_id, title, folder)` triple is idempotent — second
  apply is an update to the same dashboard, not a duplicate.

## Backward-compat
Drafts are strictly additive. Existing dashboards are untouched until
an explicit **apply** on an edit flow.
