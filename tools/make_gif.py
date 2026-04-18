"""Generate an animated GIF demo for O11yBot — shows Home page → Dashboards with widget always visible.

Journey:
  1. Grafana Home page (o11Y Place) + pulsing bubble
  2. User clicks bubble → chat opens
  3. User asks "list all dashboards" → streaming response
  4. Navigate to AKS dashboard — bubble stays!
  5. User asks "check grafana health" → quick reply
  6. Navigate to Logs view — bubble still there
  7. Maximize on Logs
  8. Fullscreen showing advantages
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pathlib import Path
import math, os

W, H = 900, 560
OUT = Path("/Volumes/Gopalmac/Gopal-aiops/ollychat-app/docs/assets/o11ybot-demo.gif")
OUT.parent.mkdir(parents=True, exist_ok=True)

# ─── Colors ───
BG_TOP = (22, 22, 38)
BG_BOTTOM = (11, 13, 20)
ORANGE = (255, 102, 0)
AMBER = (245, 158, 11)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
BLUE = (96, 165, 250)
BLUE_DEEP = (37, 99, 235)
PURPLE = (167, 139, 250)
TEXT = (230, 230, 230)
TEXT_DIM = (150, 150, 150)
TEXT_FAINT = (90, 90, 90)
PANEL = (24, 27, 35)
PANEL_DARK = (15, 17, 23)
PANEL_HEADER = (26, 16, 37)
BORDER = (42, 42, 62)
USER_BUB = (30, 58, 95)


def load_font(size):
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/SFNS.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    return ImageFont.load_default()


F_XS = load_font(9)
F_SM = load_font(11)
F_MD = load_font(13)
F_LG = load_font(16)
F_XL = load_font(20)
F_XXL = load_font(32)


def gradient_bg(img):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def grafana_nav(draw, breadcrumb="Home"):
    draw.rectangle([0, 0, W, 44], fill=(8, 10, 16))
    draw.ellipse([14, 14, 34, 34], fill=(240, 90, 40))
    draw.ellipse([19, 19, 29, 29], fill=(8, 10, 16))
    draw.text((48, 15), breadcrumb, fill=TEXT, font=F_MD)
    draw.rounded_rectangle([W//2 - 120, 10, W//2 + 120, 32], radius=4, fill=(20, 22, 30))
    draw.text((W//2 - 110, 14), "🔍 Search or jump to...", fill=(100, 100, 100), font=F_SM)
    draw.text((W//2 + 95, 14), "⌘K", fill=(80, 80, 80), font=F_SM)
    draw.ellipse([W - 30, 12, W - 12, 30], fill=(37, 99, 235, 100), outline=BLUE)
    draw.text((W - 25, 14), "A", fill=BLUE, font=F_SM)


def left_sidebar(draw, active=0):
    draw.rectangle([0, 44, 56, H], fill=(8, 10, 16))
    icons = ["🏠", "📊", "🔍", "🔔", "⚙️"]
    for i, ic in enumerate(icons):
        y = 70 + i * 40
        if i == active:
            draw.rectangle([0, y - 10, 4, y + 20], fill=AMBER)
        draw.text((18, y - 2), ic, fill=(180, 180, 180) if i == active else (100, 100, 100), font=F_LG)


# ─── Page: Grafana Home (like user's screenshot) ───
def page_home(draw):
    grafana_nav(draw, "Home")
    left_sidebar(draw, active=0)

    # Welcome banner
    draw.text((80, 78), "Welcome to ", fill=TEXT, font=F_XL)
    draw.text((228, 78), "o11Y Place", fill=AMBER, font=F_XL)
    draw.text((358, 78), ", 👋 ", fill=TEXT, font=F_XL)
    draw.text((412, 78), "admin", fill=BLUE, font=F_XL)

    # Time on right
    draw.text((W - 110, 65), "09:29", fill=TEXT, font=F_XL)
    draw.text((W - 125, 92), "SAT, APR 18", fill=TEXT_DIM, font=F_XS)

    # Hero Grafana logo
    cx, cy = W // 2, 210
    # Dotted orbit
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        dx = int(cx + 55 * math.cos(rad))
        dy = int(cy + 25 * math.sin(rad))
        draw.ellipse([dx - 2, dy - 2, dx + 2, dy + 2], fill=(255, 102, 0, 100))
    # Core circles
    for r, op in [(32, 40), (26, 80), (20, 120), (14, 160)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 102, 0, op))
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=AMBER)

    # Grafana title
    draw.text((cx - 58, cy + 55), "Grafana", fill=TEXT, font=F_XXL)
    draw.text((cx - 120, cy + 98), "ENTERPRISE OBSERVABILITY PLATFORM", fill=TEXT_DIM, font=F_XS)

    # Search bar
    sy = cy + 135
    draw.rounded_rectangle([150, sy, W - 150, sy + 34], radius=6, fill=PANEL, outline=BORDER)
    draw.text((165, sy + 9), "🔍", fill=TEXT_DIM, font=F_MD)
    draw.text((195, sy + 11), "Search dashboards, alerts, data sources...", fill=TEXT_FAINT, font=F_SM)

    # 6 KPI buttons
    btns = [("⭐", "Starred", (250, 204, 21)),
            ("🔍", "Explore", (96, 165, 250)),
            ("📊", "Drilldown", (34, 197, 94)),
            ("🔔", "Alerts", (245, 158, 11)),
            ("🗄", "Data Sources", (139, 92, 246)),
            ("⚙", "Admin", (236, 72, 153))]
    btn_w, btn_gap = 104, 10
    total_w = len(btns) * btn_w + (len(btns) - 1) * btn_gap
    bx0 = (W - total_w) // 2
    by = sy + 55
    for i, (ic, label, color) in enumerate(btns):
        x = bx0 + i * (btn_w + btn_gap)
        draw.rounded_rectangle([x, by, x + btn_w, by + 70], radius=8, fill=PANEL, outline=BORDER)
        draw.ellipse([x + btn_w // 2 - 14, by + 10, x + btn_w // 2 + 14, by + 38],
                     fill=(*color, 50), outline=color)
        draw.text((x + btn_w // 2 - 7, by + 14), ic, fill=color, font=F_MD)
        tw = len(label) * 6
        draw.text((x + btn_w // 2 - tw // 2, by + 48), label, fill=TEXT, font=F_SM)

    # Stats row at bottom
    sty = H - 30
    draw.ellipse([295, sty + 5, 305, sty + 15], fill=GREEN)
    draw.text((312, sty + 3), "113 dashboards", fill=TEXT_DIM, font=F_SM)
    draw.ellipse([430, sty + 5, 440, sty + 15], fill=GREEN)
    draw.text((447, sty + 3), "0 firing", fill=TEXT_DIM, font=F_SM)
    draw.ellipse([525, sty + 5, 535, sty + 15], fill=BLUE)
    draw.text((542, sty + 3), "1 data source", fill=TEXT_DIM, font=F_SM)


# ─── Page: AKS Dashboard ───
def page_aks(draw):
    grafana_nav(draw, "/ Dashboards / AKS — Cluster Overview")
    left_sidebar(draw, active=1)

    draw.text((80, 62), "AKS — Cluster Overview & Health", fill=TEXT, font=F_LG)
    draw.text((80, 85), "Azure · Kubernetes · Last 6 hours · auto-refresh 30s", fill=TEXT_DIM, font=F_SM)

    kpis = [("Cluster", "Healthy", GREEN, "3/3 nodes"),
            ("Pods", "247", BLUE, "+12 /1h"),
            ("CPU", "64.2%", AMBER, "P95: 78%"),
            ("Errors", "0.42%", RED, "↑ 0.12%")]
    kw, kgap, kx0 = 170, 10, 80
    for i, (label, val, color, sub) in enumerate(kpis):
        x = kx0 + i * (kw + kgap)
        draw.rounded_rectangle([x, 110, x + kw, 200], radius=8, fill=PANEL, outline=BORDER)
        draw.text((x + 12, 120), label, fill=TEXT_DIM, font=F_SM)
        draw.text((x + 12, 140), val, fill=color, font=F_XL)
        draw.text((x + 12, 180), sub, fill=TEXT_FAINT, font=F_XS)

    # Chart
    draw.rounded_rectangle([80, 215, 560, 420], radius=8, fill=PANEL, outline=BORDER)
    draw.text((92, 227), "CPU / Memory by Pod", fill=TEXT, font=F_SM)
    for y in [260, 300, 340, 380]:
        for x in range(90, 550, 8):
            draw.line([(x, y), (x + 3, y)], fill=(40, 40, 55), width=1)
    pts1 = [(95 + i * 36, 360 - int(30 * math.sin(i * 0.6)) - i * 2) for i in range(13)]
    pts2 = [(95 + i * 36, 380 - int(20 * math.cos(i * 0.5)) - i) for i in range(13)]
    for i in range(len(pts1) - 1):
        draw.line([pts1[i], pts1[i + 1]], fill=AMBER, width=2)
        draw.line([pts2[i], pts2[i + 1]], fill=BLUE, width=2)
    draw.ellipse([95, 402, 103, 410], fill=AMBER)
    draw.text((108, 400), "CPU cores", fill=TEXT_DIM, font=F_XS)
    draw.ellipse([175, 402, 183, 410], fill=BLUE)
    draw.text((188, 400), "Memory GB", fill=TEXT_DIM, font=F_XS)

    # Namespaces
    draw.rounded_rectangle([580, 215, 870, 310], radius=8, fill=PANEL, outline=BORDER)
    draw.text((592, 227), "Top Namespaces", fill=TEXT, font=F_SM)
    ns = [("production", 0.78, GREEN), ("staging", 0.45, BLUE), ("monitoring", 0.22, AMBER)]
    for i, (name, frac, color) in enumerate(ns):
        y = 250 + i * 22
        draw.text((592, y), name, fill=TEXT, font=F_XS)
        draw.rounded_rectangle([592, y + 12, 860, y + 16], radius=2, fill=(30, 30, 42))
        draw.rounded_rectangle([592, y + 12, 592 + int(268 * frac), y + 16], radius=2, fill=color)

    # Alerts
    draw.rounded_rectangle([580, 325, 870, 420], radius=8, fill=PANEL, outline=BORDER)
    draw.text((592, 337), "Recent Alerts", fill=TEXT, font=F_SM)
    for i, (name, color, status) in enumerate([
        ("HighMemory · payment-svc", RED, "firing · 12m"),
        ("PodRestart · cache-redis", AMBER, "pending · 28m"),
        ("DiskUsage · node-3", GREEN, "resolved · 1h")
    ]):
        y = 358 + i * 20
        draw.ellipse([592, y + 4, 600, y + 12], fill=color)
        draw.text((608, y), name, fill=TEXT, font=F_XS)
        draw.text((608, y + 11), status, fill=TEXT_FAINT, font=F_XS)


# ─── Page: Logs / Explore ───
def page_logs(draw):
    grafana_nav(draw, "/ Explore / Loki")
    left_sidebar(draw, active=2)

    draw.text((80, 62), "Loki — payment-service logs", fill=TEXT, font=F_LG)
    draw.text((80, 85), "LogQL: {service=\"payment\"} |= \"error\"  ·  Last 15m  ·  2,347 lines", fill=TEXT_DIM, font=F_SM)

    # Volume chart
    draw.rounded_rectangle([80, 105, 870, 175], radius=8, fill=PANEL, outline=BORDER)
    draw.text((92, 113), "Log Volume", fill=TEXT_DIM, font=F_XS)
    for i in range(40):
        h = 20 + abs((i * 7) % 30)
        color = RED if h > 40 else AMBER if h > 30 else GREEN
        draw.rectangle([98 + i * 19, 165 - h, 110 + i * 19, 165], fill=color)

    # Log lines
    draw.rounded_rectangle([80, 185, 870, H - 60], radius=8, fill=PANEL_DARK, outline=BORDER)
    logs = [
        ("14:32:01.234", "INFO", GREEN, "payment", "request received POST /api/v1/charge"),
        ("14:32:01.245", "DEBUG", BLUE, "payment", "validating payment method user_id=8492"),
        ("14:32:01.289", "INFO", GREEN, "payment", "stripe.charge.create amount=249.00"),
        ("14:32:02.103", "INFO", GREEN, "payment", "charge successful · ch_3OBc7..."),
        ("14:32:02.105", "DEBUG", BLUE, "payment", "queuing webhook delivery"),
        ("14:32:03.211", "WARN", AMBER, "payment", "retry #2 for webhook to merchant-42"),
        ("14:32:05.332", "ERROR", RED, "payment", "connection pool exhausted · pgbouncer"),
        ("14:32:05.335", "ERROR", RED, "payment", "tx rollback · could not acquire conn"),
        ("14:32:05.512", "INFO", GREEN, "payment", "healthcheck ok · 12ms"),
        ("14:32:06.001", "INFO", GREEN, "payment", "request received POST /api/v1/refund"),
        ("14:32:06.445", "INFO", GREEN, "payment", "refund processed · re_3OBc8..."),
        ("14:32:07.122", "WARN", AMBER, "payment", "slow query detected · 1.2s"),
        ("14:32:08.334", "INFO", GREEN, "payment", "metrics reported to prometheus"),
    ]
    y = 198
    for ts, lvl, color, svc, msg in logs:
        draw.text((92, y), ts, fill=TEXT_FAINT, font=F_XS)
        draw.text((175, y), lvl, fill=color, font=F_XS)
        draw.text((215, y), svc, fill=PURPLE, font=F_XS)
        draw.text((285, y), msg, fill=TEXT, font=F_XS)
        y += 19


# ─── O11yBot widget (bubble or panel) ───
def draw_fab(img, pulse=0):
    draw = ImageDraw.Draw(img)
    cx, cy = 845, 500
    r = 30
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    alpha = 90 + pulse * 3
    gd.ellipse([cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12],
               fill=(255, 102, 0, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=12))
    img.paste(glow, (0, 0), glow)
    for i in range(r, 0, -1):
        t = (r - i) / r
        rr = int(255 * (1 - t) + 245 * t)
        gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(rr, gg, 0))
    draw.rounded_rectangle([cx - 12, cy - 7, cx + 12, cy + 9], radius=5, fill=(255, 255, 255))
    draw.ellipse([cx - 7, cy - 4, cx - 3, cy], fill=(26, 26, 46))
    draw.ellipse([cx + 3, cy - 4, cx + 7, cy], fill=(26, 26, 46))
    draw.arc([cx - 4, cy + 1, cx + 4, cy + 6], 0, 180, fill=(26, 26, 46), width=2)
    draw.ellipse([cx + 16, cy - 26, cx + 28, cy - 14], fill=GREEN, outline=(13, 13, 18), width=2)


def draw_chat_panel(img, mode="normal", user_msg=None, bot_response=None, type_progress=100):
    draw = ImageDraw.Draw(img)

    if mode == "normal":
        px, py, pw, ph = 540, 80, 340, 440
    elif mode == "maximized":
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 140))
        img.paste(overlay, (0, 0), overlay)
        px, py, pw, ph = 120, 80, 660, 420

    # Shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([px - 6, py - 6, px + pw + 6, py + ph + 6], radius=16, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))
    img.paste(shadow, (0, 0), shadow)

    border_color = AMBER if mode == "maximized" else BORDER
    border_width = 2 if mode == "maximized" else 1
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=12,
                           fill=(17, 18, 23), outline=border_color, width=border_width)

    # Header
    draw.rectangle([px, py, px + pw, py + 52], fill=PANEL_HEADER)
    bx, by = px + 30, py + 26
    for i in range(17, 0, -1):
        t = (17 - i) / 17
        rr = int(255 * (1 - t) + 245 * t)
        gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([bx - i, by - i, bx + i, by + i], fill=(rr, gg, 0))
    draw.rounded_rectangle([bx - 8, by - 5, bx + 8, by + 7], radius=3, fill=(255, 255, 255))
    draw.ellipse([bx - 5, by - 3, bx - 2, by], fill=(26, 26, 46))
    draw.ellipse([bx + 2, by - 3, bx + 5, by], fill=(26, 26, 46))
    draw.text((bx + 20, py + 13), "O11yBot", fill=(255, 255, 255), font=F_MD)
    subtitle = "⚡ MAXIMIZED" if mode == "maximized" else "O11y Assistant · drag to move"
    sub_color = AMBER if mode == "maximized" else TEXT_DIM
    draw.text((bx + 20, py + 30), subtitle, fill=sub_color, font=F_XS)

    # Window buttons
    btns = [("clear", False), ("min", False), ("max", mode == "maximized"), ("full", False)]
    bw, bgap = 26, 4
    btn_x = px + pw - len(btns) * (bw + bgap) - 4
    for label, active in btns:
        if active:
            draw.rounded_rectangle([btn_x, py + 13, btn_x + bw, py + 39], radius=5,
                                   fill=(60, 25, 10), outline=AMBER)
            c = AMBER
        else:
            draw.rounded_rectangle([btn_x, py + 13, btn_x + bw, py + 39], radius=5, outline=BORDER)
            c = TEXT_DIM
        if label == "min":
            draw.line([(btn_x + 8, py + 26), (btn_x + 18, py + 26)], fill=c, width=2)
        elif label == "max":
            draw.rectangle([btn_x + 8, py + 19, btn_x + 18, py + 33], outline=c, width=1)
        elif label == "full":
            draw.line([(btn_x + 7, py + 22), (btn_x + 7, py + 18), (btn_x + 11, py + 18)], fill=c, width=1)
            draw.line([(btn_x + 15, py + 18), (btn_x + 19, py + 18), (btn_x + 19, py + 22)], fill=c, width=1)
            draw.line([(btn_x + 7, py + 30), (btn_x + 7, py + 34), (btn_x + 11, py + 34)], fill=c, width=1)
            draw.line([(btn_x + 15, py + 34), (btn_x + 19, py + 34), (btn_x + 19, py + 30)], fill=c, width=1)
        elif label == "clear":
            draw.rectangle([btn_x + 8, py + 21, btn_x + 18, py + 32], outline=c, width=1)
            draw.line([(btn_x + 6, py + 21), (btn_x + 20, py + 21)], fill=c, width=1)
        btn_x += bw + bgap

    body_y = py + 62

    if user_msg is None:
        # Welcome
        draw.text((px + pw // 2 - 45, body_y + 50), "Hey Admin!", fill=(255, 255, 255), font=F_LG)
        draw.text((px + pw // 2 - 125, body_y + 75), "Ask about dashboards, metrics,", fill=TEXT_DIM, font=F_SM)
        draw.text((px + pw // 2 - 85, body_y + 92), "logs, or incidents.", fill=TEXT_DIM, font=F_SM)
        suggs = ["List all Grafana dashboards", "List datasources", "Check Grafana health", "List folders"]
        for i, s in enumerate(suggs):
            y = body_y + 130 + i * 34
            draw.rounded_rectangle([px + 20, y, px + pw - 20, y + 26], radius=6, fill=PANEL, outline=BORDER)
            draw.text((px + 32, y + 6), s, fill=TEXT, font=F_SM)
    else:
        # User msg
        uw = min(len(user_msg) * 7 + 24, 260)
        ux = px + pw - 40 - uw
        uy = body_y
        draw.rounded_rectangle([ux, uy, ux + uw, uy + 30], radius=10, fill=USER_BUB, outline=BLUE_DEEP)
        draw.text((ux + 10, uy + 8), user_msg, fill=(207, 226, 255), font=F_SM)
        draw.ellipse([px + pw - 34, uy + 4, px + pw - 14, uy + 24], fill=(37, 99, 235, 60), outline=BLUE)
        draw.text((px + pw - 28, uy + 5), "A", fill=BLUE, font=F_SM)

        if bot_response:
            bot_y = uy + 48
            draw.ellipse([px + 12, bot_y + 2, px + 32, bot_y + 22], fill=(60, 25, 10), outline=AMBER)
            draw.text((px + 18, bot_y + 5), "O", fill=AMBER, font=F_SM)

            # Tool indicator
            draw.rounded_rectangle([px + 40, bot_y, px + pw - 14, bot_y + 22], radius=5,
                                   fill=PANEL_DARK, outline=BORDER)
            draw.ellipse([px + 48, bot_y + 8, px + 54, bot_y + 14], fill=GREEN)
            tool = bot_response.get("tool", "")
            draw.text((px + 60, bot_y + 4), tool, fill=AMBER, font=F_XS)
            draw.text((px + 60 + len(tool) * 6 + 8, bot_y + 4),
                      f"· {bot_response.get('duration', 114)}ms · ✓",
                      fill=TEXT_DIM, font=F_XS)

            # Response bubble
            bubble_y = bot_y + 30
            bubble_h = ph - (bubble_y - py) - 70
            draw.rounded_rectangle([px + 40, bubble_y, px + pw - 14, bubble_y + bubble_h],
                                   radius=10, fill=(26, 26, 46), outline=BORDER)

            lines = bot_response.get("lines", [])
            total = sum(len(l[0]) for l in lines)
            chars_to_show = int(total * type_progress / 100)
            used = 0
            ty = bubble_y + 10
            for text, color, font in lines:
                if used >= chars_to_show: break
                visible = text[:max(0, chars_to_show - used)] if used + len(text) > chars_to_show else text
                if visible:
                    draw.text((px + 52, ty), visible, fill=color, font=font)
                ty += 14 if font == F_XS else 18
                used += len(text)
            if chars_to_show < total:
                draw.rectangle([px + 54, ty - 14, px + 56, ty - 2], fill=AMBER)

    # Input
    iy = py + ph - 46
    draw.rectangle([px, iy, px + pw, py + ph], fill=PANEL_DARK)
    draw.rounded_rectangle([px + 10, iy + 8, px + pw - 50, iy + 38], radius=8, fill=PANEL, outline=BORDER)
    draw.text((px + 20, iy + 16), "Ask about observability...", fill=TEXT_FAINT, font=F_SM)
    # Send btn
    cx, cy2 = px + pw - 25, iy + 23
    for i in range(15, 0, -1):
        t = (15 - i) / 15
        rr = int(255 * (1 - t) + 245 * t); gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([cx - i, cy2 - i, cx + i, cy2 + i], fill=(rr, gg, 0))
    draw.text((px + pw - 30, iy + 16), "➤", fill=(255, 255, 255), font=F_MD)


def draw_fullscreen_advantages(img):
    draw = ImageDraw.Draw(img)
    grafana_nav(draw, "/ O11yBot")
    draw.rectangle([0, 44, W, H], fill=(13, 13, 20))
    draw.rectangle([0, 44, W, 100], fill=PANEL_HEADER)
    cx, cy = 40, 72
    for i in range(20, 0, -1):
        t = (20 - i) / 20
        rr = int(255 * (1 - t) + 245 * t); gg = int(102 * (1 - t) + 158 * t)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(rr, gg, 0))
    draw.rounded_rectangle([cx - 10, cy - 6, cx + 10, cy + 8], radius=4, fill=(255, 255, 255))
    draw.ellipse([cx - 6, cy - 3, cx - 2, cy + 1], fill=(26, 26, 46))
    draw.ellipse([cx + 2, cy - 3, cx + 6, cy + 1], fill=(26, 26, 46))
    draw.text((75, 54), "O11yBot", fill=(255, 255, 255), font=F_LG)
    draw.text((75, 78), "⛶ FULLSCREEN MODE", fill=AMBER, font=F_SM)

    draw.text((80, 130), "🚀 Advantages", fill=(255, 255, 255), font=F_XL)

    advantages = [
        ("✨", "Floats on EVERY Grafana page — no context switching"),
        ("🔐", "User-isolated chat history (per Grafana login)"),
        ("🛠", "16 real Grafana MCP tools — dashboards, alerts, DS"),
        ("💻", "Self-hosted LLM (Ollama) OR cloud (OpenAI/Anthropic)"),
        ("🛡", "PII detection — 15 patterns (email, SSN, API keys)"),
        ("⚡", "Intent matcher — instant tools with tiny 500MB LLM"),
        ("📊", "Full OpenTelemetry → LGTM stack"),
        ("🎯", "98/98 automated tests — production-ready"),
    ]
    for i, (emoji, text) in enumerate(advantages):
        y = 170 + i * 40
        draw.rounded_rectangle([80, y, W - 80, y + 32], radius=6, fill=PANEL, outline=BORDER)
        draw.text((95, y + 7), emoji, fill=AMBER, font=F_MD)
        draw.text((130, y + 9), text, fill=TEXT, font=F_SM)

    draw.rectangle([0, H - 30, W, H], fill=PANEL_HEADER)
    draw.ellipse([18, H - 22, 26, H - 14], fill=BLUE)
    draw.text((32, H - 23), "admin · 4 msgs", fill=TEXT_FAINT, font=F_SM)
    draw.text((W - 180, H - 23), "Press ESC to exit fullscreen", fill=TEXT_FAINT, font=F_SM)


def render(page_fn, *, fab=False, panel=False, mode="normal",
           user_msg=None, bot=None, progress=100, pulse=0, fullscreen_adv=False):
    img = Image.new("RGB", (W, H), BG_BOTTOM)
    gradient_bg(img)
    draw = ImageDraw.Draw(img)
    if fullscreen_adv:
        draw_fullscreen_advantages(img)
        return img
    page_fn(draw)
    if fab:
        draw_fab(img, pulse=pulse)
    elif panel:
        draw_chat_panel(img, mode=mode, user_msg=user_msg, bot_response=bot, type_progress=progress)
    return img


# ═══════════════════════════════════════════════════════════════
# BUILD FRAMES
# ═══════════════════════════════════════════════════════════════

frames = []

# Scene 1: Home page + pulsing bubble (12 frames)
for i in range(12):
    pulse = int(10 * abs((i % 10) - 5) / 5)
    frames.append(render(page_home, fab=True, pulse=pulse))

# Scene 2: Home + chat opens welcome (5 frames)
for _ in range(5):
    frames.append(render(page_home, panel=True))

# Scene 3: User asks "list dashboards" — streaming (10 frames)
dashboards_resp = {
    "tool": "list_dashboards", "duration": 114,
    "lines": [
        ("**Found 113 dashboards:**", (255, 255, 255), F_SM),
        ("", TEXT, F_SM),
        ("• AKS — Cluster Overview", (255, 255, 255), F_SM),
        ("  folder: Azure", TEXT_DIM, F_XS),
        ("• Azure — App Insights", (255, 255, 255), F_SM),
        ("  folder: Azure", TEXT_DIM, F_XS),
        ("• Albertsons — Home", (255, 255, 255), F_SM),
        ("  folder: Platform", TEXT_DIM, F_XS),
        ("• Loki Write QoS", (255, 255, 255), F_SM),
        ("  folder: Loki", TEXT_DIM, F_XS),
        ("", TEXT, F_SM),
        ("…and 109 more", TEXT_DIM, F_SM),
    ],
}
for progress in [5, 20, 40, 65, 85, 100, 100, 100]:
    frames.append(render(page_home, panel=True,
                         user_msg="list all Grafana dashboards",
                         bot=dashboards_resp, progress=progress))

# Scene 4: Navigate to AKS dashboard - bubble follows (5 frames)
for _ in range(5):
    frames.append(render(page_aks, fab=True, pulse=5))

# Scene 5: Chat on AKS dashboard, asks about health (6 frames)
health_resp = {
    "tool": "health_check", "duration": 42,
    "lines": [
        ("**Grafana Health**", (255, 255, 255), F_SM),
        ("", TEXT, F_SM),
        ("• Version: 11.6.4", AMBER, F_SM),
        ("• Database: ✓ ok", GREEN, F_SM),
        ("• Datasources: 3", TEXT, F_SM),
        ("  Mimir, Loki, Tempo", BLUE, F_XS),
    ],
}
for progress in [20, 50, 80, 100, 100, 100]:
    frames.append(render(page_aks, panel=True,
                         user_msg="check grafana health",
                         bot=health_resp, progress=progress))

# Scene 6: Navigate to Logs page - bubble STILL there (5 frames)
for _ in range(5):
    frames.append(render(page_logs, fab=True, pulse=5))

# Scene 7: Maximized mode on Logs (6 frames)
ds_resp = {
    "tool": "list_datasources", "duration": 38,
    "lines": [
        ("**Found 3 datasources:**", (255, 255, 255), F_SM),
        ("", TEXT, F_SM),
        ("• Mimir ⭐ default", (255, 255, 255), F_SM),
        ("  type: prometheus", TEXT_DIM, F_XS),
        ("• Loki", (255, 255, 255), F_SM),
        ("  type: loki", TEXT_DIM, F_XS),
        ("• Tempo", (255, 255, 255), F_SM),
        ("  type: tempo", TEXT_DIM, F_XS),
    ],
}
for _ in range(6):
    frames.append(render(page_logs, panel=True, mode="maximized",
                         user_msg="list datasources",
                         bot=ds_resp, progress=100))

# Scene 8: Fullscreen advantages (10 frames)
for _ in range(10):
    frames.append(render(page_logs, fullscreen_adv=True))


print(f"Total frames: {len(frames)}")

frames[0].save(
    OUT,
    save_all=True,
    append_images=frames[1:],
    duration=180,  # 180ms per frame = ~5.5fps (readable)
    loop=0,
    optimize=True,
)

size_kb = os.path.getsize(OUT) / 1024
print(f"Saved: {OUT} ({size_kb:.1f} KB, {len(frames)} frames, {len(frames) * 0.18:.1f}s loop)")


# Also save key frames as static screenshots
SCREENSHOTS = Path("/Volumes/Gopalmac/Gopal-aiops/ollychat-app/docs/assets")

# Home with bubble
render(page_home, fab=True, pulse=10).save(SCREENSHOTS / "screenshot-home-bubble.png", optimize=True)
# Home with chat
render(page_home, panel=True, user_msg="list all Grafana dashboards",
       bot=dashboards_resp, progress=100).save(SCREENSHOTS / "screenshot-home-chat.png", optimize=True)
# AKS with bubble
render(page_aks, fab=True, pulse=10).save(SCREENSHOTS / "screenshot-aks-bubble.png", optimize=True)
# AKS with chat
render(page_aks, panel=True, user_msg="check grafana health",
       bot=health_resp, progress=100).save(SCREENSHOTS / "screenshot-aks-chat.png", optimize=True)
# Logs with maximized
render(page_logs, panel=True, mode="maximized",
       user_msg="list datasources", bot=ds_resp, progress=100).save(SCREENSHOTS / "screenshot-logs-maximized.png", optimize=True)
# Fullscreen advantages
render(page_logs, fullscreen_adv=True).save(SCREENSHOTS / "screenshot-fullscreen.png", optimize=True)

print(f"\nStatic screenshots saved to {SCREENSHOTS}/")
for p in SCREENSHOTS.glob("screenshot-*.png"):
    print(f"  {p.name} ({p.stat().st_size // 1024} KB)")
