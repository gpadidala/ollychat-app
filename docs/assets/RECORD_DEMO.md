# How to Record the Demo GIF

The README references `docs/assets/o11ybot-demo.gif`. Here's how to create it.

## Tools (pick one)

### Mac
- **[Kap](https://getkap.co/)** (recommended) — free, native, exports GIF directly
- **[Gifox](https://gifox.io/)** — $5 Mac App Store
- **[LICEcap](https://www.cockos.com/licecap/)** — free, lightweight

### Cross-platform
- **[ScreenToGif](https://www.screentogif.com/)** (Windows)
- **[Peek](https://github.com/phw/peek)** (Linux)
- **[asciinema](https://asciinema.org/)** → convert to GIF with `agg`

## Recording Checklist

1. Hard-refresh Grafana at `http://localhost:3200` (admin/admin)
2. Open a pretty dashboard (e.g., Albertsons Home)
3. Position Kap/recorder to ~900x600 region, centered on the O11yBot bubble area
4. Start recording at **10-15 fps** (keeps GIF small)

## Demo Script (~20 seconds)

Total recording ~20 seconds, which at 15fps = ~300 frames:

| Time | Action |
|---|---|
| 0-2s | Click orange bubble to open widget |
| 2-6s | Type "list all Grafana dashboards" and hit Enter |
| 6-10s | Dashboards stream in |
| 10-12s | Click maximize button (□) — expands to 75% viewport |
| 12-14s | Click fullscreen button (⛶) — fills screen |
| 14-15s | Press Esc — returns to normal |
| 15-17s | Drag header to move the widget |
| 17-19s | Type "check grafana health" → streams health response |
| 19-20s | Click minimize — back to bubble |

## Post-processing

Keep GIF under **5 MB** for fast README load:
```bash
# Optimize with gifsicle
brew install gifsicle
gifsicle -O3 --lossy=80 --colors 128 o11ybot-demo.gif -o o11ybot-demo.gif

# Or ffmpeg-based (better quality/size ratio)
brew install ffmpeg
ffmpeg -i o11ybot-demo.mp4 \
  -vf "fps=12,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  -loop 0 o11ybot-demo.gif
```

## Target specs

- Dimensions: **800px wide** (fits GitHub README)
- Frame rate: **10-15 fps**
- Duration: **15-25 seconds**
- Size: **< 5 MB**
- Format: GIF (auto-plays in README)

Save final file at:
```
docs/assets/o11ybot-demo.gif
```
