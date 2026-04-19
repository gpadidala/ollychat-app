# Recording a premium demo

The README banner is a live, Playwright-driven capture — not a hand-crafted mock.
This guide reproduces it end-to-end in one command.

## What you get

| File | Purpose |
|---|---|
| `docs/assets/hero-home.png`      | Grafana Home with the floating FAB |
| `docs/assets/hero-chat.png`      | Chat panel mid-conversation |
| `docs/assets/hero-response.png`  | Streaming tool-call response |
| `docs/assets/hero-wizard.png`    | Dashboard-creation wizard |
| `docs/assets/hero-maximized.png` | Maximised workspace |
| `docs/assets/demo.webm`          | Full 20-second recording |
| `docs/assets/demo.gif`           | Optimised GIF for the README |

All are retina-scaled (`device_scale_factor=2`) then downscaled to keep page
weight reasonable.

## Prerequisites

```bash
# one-time
pip install playwright
playwright install chromium
brew install ffmpeg           # or apt-get install ffmpeg
```

A live Grafana the widget is loaded into must be reachable. Either:
- run `docker compose up -d` from the repo root (bundled Grafana on `:3002` with
  the plugin already mounted), **or**
- point at your own Grafana where the plugin has been installed per
  [INSTALLATION.md](../INSTALLATION.md).

## One-liner capture

```bash
python3 docs/assets/capture-demo.py \
    --grafana-url http://localhost:3200 \
    --user admin \
    --password admin
```

A real Chrome window opens, Playwright drives it through the scenario, the
script quits, and `docs/assets/` is refreshed with new assets. The whole run
takes ~45 seconds.

## What the script does

1. **Login** to Grafana.
2. Opens the home page and waits for `#o11ybot-root` to appear.
3. Clicks the FAB and sends `list all dashboards`.
4. Sends `which dashboards use metric grafana_http_request_duration_seconds_bucket`
   — snapshots mid-stream so the reader sees the tool call in flight.
5. Maximises the window.
6. Sends `create a grafana latency dashboard` to trigger the wizard response.
7. Finalises the video + regenerates the GIF via ffmpeg.

Every step has a bounded wait so the capture is deterministic across runs.

## Re-styling the recording

Edit the `capture` function in [`capture-demo.py`](capture-demo.py):

- **Window size** — change `VIEWPORT = {"width": 1600, "height": 1000}`.
- **Retina quality** — `DEVICE_SCALE` (1 = 1x, 2 = retina).
- **Speed** — `type_and_send(... delay=22)` — milliseconds between keystrokes.
- **Scenarios** — append more `type_and_send` / screenshot calls to the tail.

## GIF size tuning

The script pipes the recording through ffmpeg with `fps=12, scale=960`, a
128-colour palette and Bayer dither — that lands most runs in the **3–5 MB**
zone. If you need smaller, tweak in the script or re-encode manually:

```bash
cd docs/assets
ffmpeg -y -i demo.webm -vf fps=10,scale=800:-1:flags=lanczos,palettegen=max_colors=96 palette.png
ffmpeg -y -i demo.webm -i palette.png \
  -lavfi "fps=10,scale=800:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" \
  demo.gif
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Timeout 30000ms exceeded` on `page.goto` | Grafana's long-polling never satisfies `networkidle`. The script already uses `domcontentloaded`; confirm you're on the current version. |
| `.ob-fab` never appears | The widget script isn't being injected. Verify `grafana-index.html` is mounted. |
| `hero-chat.png` is blank | Raise the `min_chars=200` threshold in `wait_for_response` — local Ollama is slower on cold start. |
| GIF too large for GitHub | Drop fps to 8 or width to 720 in the ffmpeg re-encode step above. |
