"""Premium demo capture — drives Grafana + O11yBot widget with Playwright
and produces:

    docs/assets/hero-home.png         — Grafana home with the FAB visible
    docs/assets/hero-chat.png         — Chat panel mid-conversation
    docs/assets/hero-response.png     — Streaming response with tool badge
    docs/assets/hero-maximized.png    — Maximized window showing full thread
    docs/assets/hero-wizard.png       — Dashboard-creation wizard in action
    docs/assets/demo.webm             — Full 20-second recording
    docs/assets/demo.gif              — Optimised GIF (via ffmpeg, if present)

Run:

    python3 docs/assets/capture-demo.py \\
        --grafana-url http://localhost:3200 \\
        --user admin --pass admin

Prereqs:

    pip install playwright
    playwright install chromium
    brew install ffmpeg   # optional, only for the GIF step
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

OUT = Path(__file__).parent.resolve()
VIEWPORT = {"width": 1600, "height": 1000}
DEVICE_SCALE = 2   # retina-quality PNGs


async def login(page: Page, base: str, user: str, pw: str) -> None:
    await page.goto(f"{base}/login", wait_until="domcontentloaded")
    await asyncio.sleep(1.0)
    try:
        await page.fill('input[name="user"]', user, timeout=5000)
        await page.fill('input[name="password"]', pw, timeout=5000)
        await page.click('button[type="submit"]', timeout=5000)
        await asyncio.sleep(2.5)
    except Exception as e:
        print("  (login skipped —", str(e)[:80], ")")
    try:
        await page.click("text=Skip", timeout=2000)
    except Exception:
        pass


async def wait_for_widget(page: Page) -> None:
    # The FAB should appear once o11ybot-widget.js runs
    await page.wait_for_selector("#o11ybot-root", timeout=15000)
    await asyncio.sleep(1.2)  # let fade-in animation settle


async def open_chat(page: Page) -> None:
    fab = page.locator(".ob-fab, .ob-bubble").first
    await fab.click()
    await page.wait_for_selector(".ob-panel", timeout=5000)
    await asyncio.sleep(0.8)


async def type_and_send(page: Page, text: str) -> None:
    box = page.locator(".ob-in").first
    await box.click()
    await box.fill("")
    await box.type(text, delay=22)
    await asyncio.sleep(0.4)
    await page.keyboard.press("Enter")


async def wait_for_response(page: Page, min_chars: int = 120, timeout_s: int = 20) -> None:
    # Wait for at least <min_chars> of text to appear in the latest bot bubble
    for _ in range(timeout_s * 4):
        n = await page.evaluate(
            "() => { const b = document.querySelectorAll('.ob-msg-b .ob-bub'); "
            "return b.length ? (b[b.length-1].innerText||'').length : 0; }"
        )
        if n >= min_chars:
            return
        await asyncio.sleep(0.25)


async def maximize(page: Page) -> None:
    await page.click("#ob-max")
    await asyncio.sleep(0.8)


async def capture(base: str, user: str, pw: str) -> None:
    async with async_playwright() as pw_ctx:
        browser = await pw_ctx.chromium.launch(
            headless=False,
            args=[
                "--hide-scrollbars",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = await browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
            record_video_dir=str(OUT),
            record_video_size=VIEWPORT,
        )
        page = await ctx.new_page()

        # 1. Login + Grafana home
        await login(page, base, user, pw)
        await page.goto(f"{base}/?orgId=1", wait_until="domcontentloaded")
        await wait_for_widget(page)
        await page.screenshot(path=str(OUT / "hero-home.png"), full_page=False)
        print("  ✓ hero-home.png")

        # 2. Open the chat, mid-conversation
        await open_chat(page)
        await type_and_send(page, "list all dashboards")
        await wait_for_response(page, min_chars=200, timeout_s=15)
        await page.screenshot(path=str(OUT / "hero-chat.png"))
        print("  ✓ hero-chat.png")

        # 3. Streaming response — second query, capture while text is flowing
        await type_and_send(page, "which dashboards use metric grafana_http_request_duration_seconds_bucket")
        await asyncio.sleep(1.6)     # a short slice into the stream
        await page.screenshot(path=str(OUT / "hero-response.png"))
        print("  ✓ hero-response.png")
        await wait_for_response(page, min_chars=200, timeout_s=20)

        # 4. Maximized view
        await maximize(page)
        await page.screenshot(path=str(OUT / "hero-maximized.png"))
        print("  ✓ hero-maximized.png")
        await page.click("#ob-max")  # restore
        await asyncio.sleep(0.6)

        # 5. Dashboard-creation wizard
        await type_and_send(page, "create a grafana latency dashboard")
        await wait_for_response(page, min_chars=400, timeout_s=15)
        await page.screenshot(path=str(OUT / "hero-wizard.png"))
        print("  ✓ hero-wizard.png")

        # Let the video record a couple more seconds of idle
        await asyncio.sleep(2.0)

        # Finalise the video
        vid = await page.video.path() if page.video else None
        await ctx.close()
        await browser.close()

        if vid:
            target = OUT / "demo.webm"
            Path(vid).replace(target)
            print(f"  ✓ {target.name}")
            maybe_make_gif(target)


def maybe_make_gif(webm: Path) -> None:
    if not shutil.which("ffmpeg"):
        print("  (skip GIF — ffmpeg not found)")
        return
    gif = webm.with_suffix(".gif")
    palette = webm.with_suffix(".palette.png")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(webm),
             "-vf", "fps=14,scale=1200:-1:flags=lanczos,palettegen=max_colors=192",
             str(palette)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(webm), "-i", str(palette),
             "-lavfi", "fps=14,scale=1200:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
             str(gif)],
            check=True, capture_output=True,
        )
        palette.unlink(missing_ok=True)
        print(f"  ✓ {gif.name}")
    except subprocess.CalledProcessError as e:
        print("  ✗ ffmpeg failed:", e.stderr.decode()[:200])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafana-url", default="http://localhost:3200")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin")
    args = ap.parse_args()
    asyncio.run(capture(args.grafana_url, args.user, args.password))


if __name__ == "__main__":
    main()
