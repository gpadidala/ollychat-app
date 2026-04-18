"""Generate an animated GIF demo for O11yBot — styled like deepeval's README GIF.

Creates frames as PNG then combines into a GIF via PIL.
Resolution: 900x560, ~30 frames, ~3 seconds per scene, loops forever.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

W, H = 900, 560
OUT = Path("/Volumes/Gopalmac/Gopal-aiops/ollychat-app/docs/assets/o11ybot-demo.gif")
OUT.parent.mkdir(parents=True, exist_ok=True)

# Colors
BG_TOP = (26, 26, 46)
BG_BOTTOM = (13, 13, 18)
ORANGE = (255, 102, 0)
AMBER = (245, 158, 11)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
BLUE = (96, 165, 250)
PURPLE = (167, 139, 250)
TEXT = (224, 224, 224)
TEXT_DIM = (136, 136, 136)
TEXT_FAINT = (85, 85, 85)
PANEL = (17, 18, 23)
PANEL_LIGHT = (26, 16, 37)
BORDER = (42, 42, 62)
USER_BUB = (30, 58, 95)


# ── Font loading ──
def load_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


FONT_SM = load_font(10)
FONT = load_font(12)
FONT_MD = load_font(14)
FONT_LG = load_font(18)
FONT_XL = load_font(22)
FONT_XXL = load_font(28)
FONT_MONO = load_font(11)


def bg(draw):
    """Draw gradient background."""
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def grafana_chrome(draw):
    """Top nav bar."""
    draw.rectangle([0, 0, W, 48], fill=(11, 14, 19))
    draw.ellipse([18, 15, 40, 37], fill=(240, 90, 40))
    draw.text((55, 16), "Grafana", fill=(204, 204, 204), font=FONT_MD)
    draw.text((130, 18), "/ Dashboards / AKS — Cluster Overview", fill=(102, 102, 102), font=FONT)


def draw_mini_dashboard(draw):
    """Background dashboard panels (dimmed)."""
    # KPI cards
    for i, (x, label, val, color) in enumerate([
        (30, "Healthy", "3/3", GREEN),
        (180, "Pods", "247", BLUE),
        (330, "CPU", "64%", AMBER),
        (480, "Errors", "0.4%", RED),
    ]):
        draw.rounded_rectangle([x, 70, x + 140, 140], radius=6, fill=PANEL, outline=BORDER)
        draw.text((x + 10, 82), label, fill=TEXT_DIM, font=FONT_SM)
        draw.text((x + 10, 100), val, fill=color, font=FONT_XL)

    # Chart panel
    draw.rounded_rectangle([30, 155, 620, 330], radius=6, fill=PANEL, outline=BORDER)
    draw.text((40, 165), "CPU / Memory by Pod", fill=(204, 204, 204), font=FONT)
    # Gridlines
    for y in [200, 240, 280, 320]:
        draw.line([(40, y), (610, y)], fill=(30, 30, 46), width=1)
    # Orange trend line
    pts = [(40 + i * 45, 315 - (i * 4 + (i % 3) * 8)) for i in range(13)]
    draw.line(pts, fill=AMBER, width=2)
    # Blue trend
    pts2 = [(40 + i * 45, 320 - (i * 2 + (i % 4) * 3)) for i in range(13)]
    draw.line(pts2, fill=BLUE, width=2)

    # Logs panel
    draw.rounded_rectangle([30, 345, 620, 530], radius=6, fill=(15, 16, 23), outline=BORDER)
    draw.text((40, 355), "payment-service logs", fill=TEXT_DIM, font=FONT_SM)
    logs = [
        ("14:32:01", "INFO", GREEN, "request received /api/v1/charge"),
        ("14:32:01", "DEBUG", BLUE, "validating payment method"),
        ("14:32:02", "INFO", GREEN, "charged successfully — 249.00"),
        ("14:32:03", "WARN", AMBER, "retry #2 for webhook delivery"),
        ("14:32:05", "ERROR", RED, "connection pool exhausted"),
        ("14:32:05", "INFO", GREEN, "healthcheck ok · 200"),
        ("14:32:06", "INFO", GREEN, "request received /api/v1/refund"),
    ]
    for i, (ts, lvl, color, msg) in enumerate(logs):
        y = 378 + i * 20
        draw.text((40, y), ts, fill=(102, 102, 102), font=FONT_SM)
        draw.text((100, y), lvl, fill=color, font=FONT_SM)
        draw.text((142, y), msg, fill=(170, 170, 170), font=FONT_SM)


def draw_fab(img, draw, scale=1.0, pulse=0):
    """Draw floating orange bubble in bottom right."""
    cx, cy = 835, 490
    r = int(30 * scale)

    # Glow layer — draw on separate image then composite
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    alpha = 100 + pulse
    gd.ellipse([cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8],
               fill=(255, 102, 0, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=10))
    img.paste(glow, (0, 0), glow)

    # Main bubble (gradient approximated with stacked ellipses)
    for i in range(r, 0, -1):
        t = (r - i) / r
        rr = int(255 * (1 - t) + 245 * t)
        gg = int(102 * (1 - t) + 158 * t)
        bb = int(0 * (1 - t) + 11 * t)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(rr, gg, bb))

    # Bot face
    draw.rounded_rectangle([cx - 12, cy - 8, cx + 12, cy + 10], radius=5, fill=(255, 255, 255))
    draw.ellipse([cx - 7, cy - 4, cx - 3, cy], fill=(26, 26, 46))
    draw.ellipse([cx + 3, cy - 4, cx + 7, cy], fill=(26, 26, 46))
    draw.arc([cx - 5, cy + 1, cx + 5, cy + 6], 0, 180, fill=(26, 26, 46), width=2)

    # Green online dot
    draw.ellipse([cx + 18, cy - 25, cx + 30, cy - 13], fill=GREEN, outline=(13, 13, 18), width=2)


def draw_panel_header(draw, x, y, w, maximized=False, fullscreen=False):
    """Window header with controls."""
    # Panel bg
    draw.rectangle([x, y, x + w, y + 52], fill=PANEL_LIGHT)
    # Bot icon
    for i in range(16, 0, -1):
        t = (16 - i) / 16
        rr = int(255 * (1 - t) + 245 * t)
        gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([x + 26 - i, y + 26 - i, x + 26 + i, y + 26 + i], fill=(rr, gg, 0))
    draw.text((x + 20, y + 17), "🤖", fill=(255, 255, 255), font=FONT_MD)
    draw.text((x + 52, y + 12), "O11yBot", fill=(255, 255, 255), font=FONT_MD)
    status = "⛶ FULLSCREEN" if fullscreen else ("⚡ MAXIMIZED" if maximized else "O11y Assistant · drag to move")
    color = AMBER if (fullscreen or maximized) else TEXT_DIM
    draw.text((x + 52, y + 30), status, fill=color, font=FONT_SM)

    # Window control buttons
    bw = 26
    bx = x + w - 4 * (bw + 4) - 8
    for label, highlight in [("clear", False), ("min", False), ("max", maximized), ("full", fullscreen)]:
        color = (255, 102, 0, 80) if highlight else None
        if highlight:
            draw.rounded_rectangle([bx, y + 13, bx + bw, y + 39], radius=5, fill=(60, 25, 10), outline=AMBER)
        else:
            draw.rounded_rectangle([bx, y + 13, bx + bw, y + 39], radius=5, outline=BORDER)
        if label == "clear":
            draw.rectangle([bx + 8, y + 20, bx + 18, y + 32], outline=TEXT_DIM, width=1)
            draw.line([(bx + 6, y + 20), (bx + 20, y + 20)], fill=TEXT_DIM, width=1)
        elif label == "min":
            draw.line([(bx + 8, y + 26), (bx + 18, y + 26)], fill=TEXT_DIM if not highlight else AMBER, width=2)
        elif label == "max":
            draw.rectangle([bx + 8, y + 19, bx + 18, y + 33], outline=TEXT_DIM if not highlight else AMBER, width=1)
        elif label == "full":
            c = TEXT_DIM if not highlight else AMBER
            draw.line([(bx + 7, y + 22), (bx + 7, y + 18), (bx + 11, y + 18)], fill=c, width=1)
            draw.line([(bx + 15, y + 18), (bx + 19, y + 18), (bx + 19, y + 22)], fill=c, width=1)
            draw.line([(bx + 7, y + 30), (bx + 7, y + 34), (bx + 11, y + 34)], fill=c, width=1)
            draw.line([(bx + 15, y + 34), (bx + 19, y + 34), (bx + 19, y + 30)], fill=c, width=1)
        bx += bw + 4


# ═══════════════════════════════════════════════════════════════
# SCENE BUILDERS
# ═══════════════════════════════════════════════════════════════

def scene_1_fab(pulse_frame):
    """Scene 1: Just the bubble, pulsing."""
    img = Image.new("RGB", (W, H), BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    bg(draw)
    grafana_chrome(draw)
    draw_mini_dashboard(draw)
    # Pulse effect
    pulse = int(30 * abs((pulse_frame % 20) - 10) / 10)
    scale = 1.0 + (pulse / 100)
    draw_fab(img, draw, scale=scale, pulse=pulse * 2)
    # Hint label
    draw.rounded_rectangle([680, 475, 810, 505], radius=6, fill=(13, 13, 18), outline=AMBER)
    draw.text((690, 484), "Click to chat →", fill=AMBER, font=FONT)
    return img


def scene_2_panel_empty():
    """Scene 2: Panel just opened, empty."""
    img = Image.new("RGB", (W, H), BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    bg(draw)
    grafana_chrome(draw)
    draw_mini_dashboard(draw)
    # Panel
    px, py, pw, ph = 540, 60, 340, 480
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([px - 4, py - 4, px + pw + 4, py + ph + 4], radius=14, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    img.paste(shadow, (0, 0), shadow)
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=12, fill=PANEL, outline=BORDER)
    draw_panel_header(draw, px, py, pw)

    # Welcome screen
    draw.text((px + pw // 2 - 80, py + 130), "Hey Admin!", fill=(255, 255, 255), font=FONT_LG)
    draw.text((px + pw // 2 - 140, py + 160), "Ask me about dashboards, metrics,", fill=TEXT_DIM, font=FONT)
    draw.text((px + pw // 2 - 100, py + 178), "logs, traces, or alerts.", fill=TEXT_DIM, font=FONT)

    # Suggestion buttons
    suggs = [
        "List all Grafana dashboards",
        "List datasources",
        "Check Grafana health",
        "List folders",
    ]
    for i, s in enumerate(suggs):
        y = py + 220 + i * 36
        draw.rounded_rectangle([px + 20, y, px + pw - 20, y + 28], radius=6, fill=(24, 27, 35), outline=BORDER)
        draw.text((px + 32, y + 8), s, fill=TEXT, font=FONT)

    # Input
    draw.rectangle([px, py + ph - 50, px + pw, py + ph], fill=(13, 13, 18))
    draw.rounded_rectangle([px + 10, py + ph - 40, px + pw - 50, py + ph - 10], radius=8, fill=(24, 27, 35), outline=BORDER)
    draw.text((px + 22, py + ph - 31), "Ask about observability...", fill=TEXT_FAINT, font=FONT)
    draw.rounded_rectangle([px + pw - 40, py + ph - 40, px + pw - 10, py + ph - 10], radius=8, fill=ORANGE)
    draw.text((px + pw - 28, py + ph - 31), "➤", fill=(255, 255, 255), font=FONT_MD)

    # Footer with user badge
    draw.ellipse([px + 14, py + ph - 68, px + 22, py + ph - 60], fill=BLUE)
    draw.text((px + 30, py + ph - 69), "admin", fill=TEXT_DIM, font=FONT_SM)

    return img


def scene_3_typing(progress_chars, maximized=False):
    """Scene 3: User typed query, bot streaming response."""
    img = Image.new("RGB", (W, H), BG_BOTTOM)
    draw = ImageDraw.Draw(img)
    bg(draw)
    grafana_chrome(draw)

    # Dim background when maximized
    if maximized:
        # Dim overlay
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
        img.paste(overlay, (0, 0), overlay)
        # Maximized panel
        px, py, pw, ph = 120, 80, 660, 420
    else:
        draw_mini_dashboard(draw)
        px, py, pw, ph = 540, 60, 340, 480

    # Panel
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([px - 4, py - 4, px + pw + 4, py + ph + 4], radius=14, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    img.paste(shadow, (0, 0), shadow)

    border_color = ORANGE if maximized else BORDER
    border_width = 2 if maximized else 1
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=12, fill=PANEL, outline=border_color, width=border_width)
    draw_panel_header(draw, px, py, pw, maximized=maximized)

    # User message
    user_msg = "list all Grafana dashboards"
    ux = px + pw - 240 - 10
    uy = py + 75
    draw.rounded_rectangle([ux, uy, px + pw - 42, uy + 28], radius=10, fill=USER_BUB, outline=(37, 99, 235))
    draw.text((ux + 12, uy + 8), user_msg, fill=(207, 226, 255), font=FONT)
    # User avatar
    draw.ellipse([px + pw - 38, uy + 4, px + pw - 16, uy + 26], fill=(37, 99, 235, 50), outline=BLUE)
    draw.text((px + pw - 31, uy + 6), "A", fill=BLUE, font=FONT)

    # Bot avatar + response
    by = uy + 50
    draw.ellipse([px + 14, by, px + 36, by + 22], fill=(60, 25, 10), outline=AMBER)
    draw.text((px + 22, by + 4), "O", fill=AMBER, font=FONT)

    # Tool call indicator (appears after initial text)
    tool_y = by - 4
    if progress_chars > 5:
        draw.rounded_rectangle([px + 44, tool_y, px + pw - 16, tool_y + 22], radius=5, fill=(13, 13, 18), outline=BORDER)
        draw.ellipse([px + 52, tool_y + 8, px + 58, tool_y + 14], fill=GREEN)
        draw.text((px + 64, tool_y + 5), "list_dashboards", fill=AMBER, font=FONT_MONO)
        draw.text((px + 158, tool_y + 5), "· 114ms · ✓ OK", fill=TEXT_DIM, font=FONT_MONO)

    # Streaming content
    full_response = [
        ("**Found 113 dashboards:**", (255, 255, 255), FONT, True),
        ("", None, None, False),
        ("• AKS — Cluster Overview & Health", (255, 255, 255), FONT, True),
        ("  folder: Azure — Cloud Infrastructure", TEXT_DIM, FONT_SM, False),
        ("  UID: aks-cluster-overview · Open ↗", BLUE, FONT_SM, False),
        ("", None, None, False),
        ("• Azure — Application Insights (APM)", (255, 255, 255), FONT, True),
        ("  folder: Azure · 24 panels", TEXT_DIM, FONT_SM, False),
        ("  UID: azure-application-insights · Open ↗", BLUE, FONT_SM, False),
        ("", None, None, False),
        ("• Albertsons — Home", (255, 255, 255), FONT, True),
        ("  folder: Platform & Executive", TEXT_DIM, FONT_SM, False),
        ("", None, None, False),
        ("…and 110 more", TEXT_DIM, FONT, False),
    ]

    response_y = tool_y + 32 if progress_chars > 5 else by
    # Response bubble
    bubble_h = 190 if not maximized else 260
    if progress_chars > 0:
        draw.rounded_rectangle([px + 44, response_y, px + pw - 16, response_y + bubble_h], radius=10, fill=(26, 26, 46), outline=BORDER)

        # Type out progressively
        total_chars = sum(len(t[0]) for t in full_response)
        chars_to_show = min(progress_chars * 4, total_chars)
        used = 0
        ly = response_y + 10
        for text, color, font, bold in full_response:
            if used >= chars_to_show:
                break
            visible = text[:max(0, chars_to_show - used)] if used + len(text) > chars_to_show else text
            if visible and color and font:
                draw.text((px + 54, ly), visible, fill=color, font=font)
            ly += 14 if font == FONT_SM else 18
            used += len(text)
        # Blinking cursor
        if chars_to_show < total_chars and progress_chars % 2 == 0:
            draw.rectangle([px + 54 + 6, ly - 14, px + 54 + 8, ly - 2], fill=AMBER)

    # Tokens + cost when done
    if progress_chars >= 16:
        draw.text((px + 54, response_y + bubble_h + 4), "54 tok", fill=TEXT_FAINT, font=FONT_MONO)
        draw.text((px + 96, response_y + bubble_h + 4), "$0.0002", fill=AMBER, font=FONT_MONO)

    # Input
    draw.rectangle([px, py + ph - 50, px + pw, py + ph], fill=(13, 13, 18))
    draw.rounded_rectangle([px + 10, py + ph - 40, px + pw - 50, py + ph - 10], radius=8, fill=(24, 27, 35), outline=BORDER)
    draw.text((px + 22, py + ph - 31), "Ask about observability...", fill=TEXT_FAINT, font=FONT)
    draw.rounded_rectangle([px + pw - 40, py + ph - 40, px + pw - 10, py + ph - 10], radius=8, fill=ORANGE)
    draw.text((px + pw - 28, py + ph - 31), "➤", fill=(255, 255, 255), font=FONT_MD)

    # Footer
    draw.ellipse([px + 14, py + ph - 68, px + 22, py + ph - 60], fill=BLUE)
    draw.text((px + 30, py + ph - 69), "admin", fill=TEXT_DIM, font=FONT_SM)
    draw.text((px + pw - 60, py + ph - 69), "2 msgs", fill=TEXT_FAINT, font=FONT_SM)

    return img


def scene_4_fullscreen():
    """Scene 4: Fullscreen mode showing advantages."""
    img = Image.new("RGB", (W, H), (13, 13, 18))
    draw = ImageDraw.Draw(img)
    grafana_chrome(draw)

    # Fullscreen header
    draw.rectangle([0, 48, W, 100], fill=PANEL_LIGHT)
    for i in range(18, 0, -1):
        t = (18 - i) / 18
        rr = int(255 * (1 - t) + 245 * t)
        gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([30 - i, 74 - i, 30 + i, 74 + i], fill=(rr, gg, 0))
    draw.text((22, 65), "🤖", fill=(255, 255, 255), font=FONT_MD)
    draw.text((60, 57), "O11yBot", fill=(255, 255, 255), font=FONT_LG)
    draw.text((60, 78), "⛶ FULLSCREEN MODE", fill=AMBER, font=FONT_SM)

    # Advantages title
    draw.text((30, 120), "🚀 Advantages", fill=(255, 255, 255), font=FONT_XL)

    advantages = [
        ("✨", "One chatbot across ALL Grafana pages — no context switching"),
        ("🔐", "User-isolated chat history (per Grafana login)"),
        ("🛠️", "16 real Grafana MCP tools — dashboards, alerts, datasources"),
        ("💻", "Self-hosted LLM (Ollama) OR cloud (OpenAI/Anthropic)"),
        ("🛡️", "PII detection with 15 patterns (email, SSN, API keys)"),
        ("⚡", "Intent matcher — reliable tool calls with tiny 500MB LLM"),
        ("📊", "Full OpenTelemetry traces + metrics to LGTM stack"),
        ("🎯", "98/98 automated tests — documented, production-ready"),
    ]
    for i, (emoji, txt) in enumerate(advantages):
        y = 170 + i * 40
        draw.rounded_rectangle([30, y, W - 30, y + 30], radius=6, fill=(24, 27, 35))
        draw.text((45, y + 6), emoji, fill=AMBER, font=FONT_MD)
        draw.text((80, y + 8), txt, fill=TEXT, font=FONT)

    # Footer
    draw.rectangle([0, H - 28, W, H], fill=PANEL_LIGHT)
    draw.ellipse([15, H - 18, 23, H - 10], fill=BLUE)
    draw.text((30, H - 20), "admin · 2 msgs", fill=TEXT_FAINT, font=FONT_SM)
    draw.text((W - 170, H - 20), "Press ESC to exit fullscreen", fill=TEXT_FAINT, font=FONT_SM)

    return img


# ═══════════════════════════════════════════════════════════════
# BUILD ANIMATION FRAMES
# ═══════════════════════════════════════════════════════════════

frames = []

# Scene 1: FAB pulsing (10 frames, 100ms each = 1s)
for i in range(10):
    frames.append(scene_1_fab(i))

# Scene 2: Panel opens (4 frames)
for _ in range(4):
    frames.append(scene_2_panel_empty())

# Scene 3: Chat normal mode — typing progression (18 frames)
for i in range(1, 19):
    frames.append(scene_3_typing(i, maximized=False))

# Scene 3 continued: hold (4 frames)
for _ in range(4):
    frames.append(scene_3_typing(20, maximized=False))

# Scene 4: Maximize transition (8 frames)
for _ in range(4):
    frames.append(scene_3_typing(20, maximized=True))
for _ in range(4):
    frames.append(scene_3_typing(20, maximized=True))

# Scene 5: Fullscreen advantages (8 frames — held)
for _ in range(8):
    frames.append(scene_4_fullscreen())

print(f"Total frames: {len(frames)}")

# Save as animated GIF
frames[0].save(
    OUT,
    save_all=True,
    append_images=frames[1:],
    duration=100,  # ms per frame
    loop=0,        # forever
    optimize=True,
)

import os
size_kb = os.path.getsize(OUT) / 1024
print(f"Saved: {OUT} ({size_kb:.1f} KB, {len(frames)} frames, {len(frames)*0.1:.1f}s loop)")
