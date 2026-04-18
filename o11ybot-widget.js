/**
 * O11yBot — Floating Grafana Chatbot Widget v1.3.0
 *
 * Rewritten with direct DOM references for reliable streaming updates.
 * Includes extensive debug logging (check browser console).
 */
(function() {
  "use strict";
  var WIDGET_VERSION = "1.3.1";
  var ORCHESTRATOR = "http://localhost:8000";
  var WIDGET_ID = "o11ybot-root";

  if (document.getElementById(WIDGET_ID)) {
    console.log("[O11yBot] Already loaded, skipping");
    return;
  }

  console.log("%c[O11yBot] v" + WIDGET_VERSION + " initializing...", "color:#f59e0b;font-weight:bold;font-size:14px;");

  // ── Get Grafana user ──
  var grafanaUser = { login: "anonymous", name: "User", orgId: 1 };
  try {
    if (window.grafanaBootData && window.grafanaBootData.user) {
      var gu = window.grafanaBootData.user;
      grafanaUser.login = gu.login || gu.email || "anonymous";
      grafanaUser.name = gu.name || gu.login || "User";
      grafanaUser.orgId = gu.orgId || 1;
    }
  } catch(e) { console.warn("[O11yBot] Could not read grafanaBootData:", e); }

  console.log("[O11yBot] User:", grafanaUser);

  var STORE_KEY = "o11ybot-" + grafanaUser.login;
  var userInitial = (grafanaUser.name || "U").charAt(0).toUpperCase();

  // ── State ──
  var state = (function() {
    try { var s = localStorage.getItem(STORE_KEY); return s ? JSON.parse(s) : {}; } catch(e) { return {}; }
  })();
  state.msgs = state.msgs || [];
  state.open = false;
  state.streaming = false;
  state.posX = state.posX != null ? state.posX : null;
  state.posY = state.posY != null ? state.posY : null;
  // mode: "normal" | "maximized" | "fullscreen"
  state.mode = state.mode || "normal";

  function saveState() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        msgs: state.msgs.slice(-100),
        posX: state.posX, posY: state.posY,
        mode: state.mode
      }));
    } catch(e) {}
  }

  // ── CSS ──
  var css = document.createElement("style");
  css.textContent = "\
#o11ybot-root{position:fixed;z-index:999999;font-family:Inter,-apple-system,sans-serif;font-size:14px;color:#e0e0e0}\
.ob-fab{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#ff6600,#f59e0b);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(255,102,0,.4),0 2px 8px rgba(0,0,0,.3);transition:transform .2s,box-shadow .2s;position:relative}\
.ob-fab:hover{transform:scale(1.1);box-shadow:0 6px 28px rgba(255,102,0,.5)}\
.ob-fab svg{width:28px;height:28px;fill:#fff}\
.ob-dot{position:absolute;top:-2px;right:-2px;width:14px;height:14px;border-radius:50%;background:#22c55e;border:2px solid #111}\
.ob-panel{width:440px;height:600px;background:#111217;border:1px solid #2a2a3e;border-radius:12px;display:flex;flex-direction:column;box-shadow:0 12px 48px rgba(0,0,0,.5);overflow:hidden;resize:both;min-width:340px;min-height:400px;max-width:90vw;max-height:85vh;transition:width .25s ease,height .25s ease,border-radius .2s ease}\
.ob-panel.ob-maximized{width:75vw!important;height:85vh!important;resize:none}\
.ob-panel.ob-fullscreen{width:100vw!important;height:100vh!important;border-radius:0;resize:none;border:none}\
#o11ybot-root.ob-maximized,#o11ybot-root.ob-fullscreen{left:0!important;top:0!important;right:0!important;bottom:0!important;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.35);backdrop-filter:blur(3px);width:100vw;height:100vh;padding:0}\
#o11ybot-root.ob-fullscreen{background:#0d0d12;padding:0}\
.ob-hdr{display:flex;align-items:center;gap:10px;padding:12px 16px;background:linear-gradient(135deg,#1a1025,#111217);border-bottom:1px solid #2a2a3e;cursor:grab;user-select:none}\
.ob-hdr:active{cursor:grabbing}\
.ob-hdr-icon{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#ff6600,#f59e0b);display:flex;align-items:center;justify-content:center;flex-shrink:0}\
.ob-hdr-icon svg{width:18px;height:18px;fill:#fff}\
.ob-title{font-weight:600;font-size:15px;flex:1}\
.ob-sub{font-size:11px;color:#888;margin-top:1px}\
.ob-acts{display:flex;gap:4px}\
.ob-hbtn{width:28px;height:28px;border-radius:6px;background:0 0;border:1px solid transparent;color:#888;cursor:pointer;display:flex;align-items:center;justify-content:center}\
.ob-hbtn:hover{background:rgba(255,255,255,.06);color:#ccc}\
.ob-hbtn svg{width:16px;height:16px;fill:currentColor}\
.ob-msgs{flex:1;overflow-y:auto;padding:16px}\
.ob-msgs::-webkit-scrollbar{width:5px}\
.ob-msgs::-webkit-scrollbar-thumb{background:#333;border-radius:3px}\
.ob-msg{margin-bottom:14px;display:flex;gap:8px}\
.ob-msg-u{flex-direction:row-reverse}\
.ob-av{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:12px;font-weight:700}\
.ob-msg-u .ob-av{background:rgba(37,99,235,.2);color:#60a5fa}\
.ob-msg-b .ob-av{background:rgba(255,102,0,.2);color:#f59e0b}\
.ob-msg-wrap{display:flex;flex-direction:column;max-width:85%}\
.ob-bub{padding:10px 14px;border-radius:12px;line-height:1.55;word-break:break-word;font-size:13.5px;min-height:20px}\
.ob-msg-u .ob-bub{background:#1e3a5f;border:1px solid rgba(37,99,235,.3);border-bottom-right-radius:4px;white-space:pre-wrap}\
.ob-msg-b .ob-bub{background:#1a1a2e;border:1px solid #2a2a3e;border-bottom-left-radius:4px}\
.ob-bub code{background:#0d0d12;padding:2px 5px;border-radius:4px;font-family:monospace;font-size:12px;color:#f59e0b}\
.ob-bub pre{background:#0d0d12;padding:10px;border-radius:6px;overflow-x:auto;margin:8px 0;font-size:12px;font-family:monospace;border:1px solid #1e1e2e}\
.ob-bub a{color:#60a5fa;text-decoration:underline}\
.ob-bub strong{color:#fff}\
.ob-bub ul{margin:8px 0;padding-left:20px}\
.ob-bub li{margin:4px 0}\
.ob-meta{font-size:11px;color:#555;margin-top:4px;display:flex;gap:8px}\
.ob-cost{color:#f59e0b;font-family:monospace}\
.ob-typing{display:flex;gap:4px;padding:4px 10px;color:#888}\
.ob-typing span{width:6px;height:6px;background:#f59e0b;border-radius:50%;animation:ob-b 1.4s infinite}\
.ob-typing span:nth-child(2){animation-delay:.2s}\
.ob-typing span:nth-child(3){animation-delay:.4s}\
@keyframes ob-b{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-8px);opacity:1}}\
.ob-in-area{padding:12px;border-top:1px solid #2a2a3e;background:#0d0d12}\
.ob-in-row{display:flex;gap:8px;align-items:flex-end}\
.ob-in{flex:1;background:#181b23;border:1px solid #2a2a3e;border-radius:8px;color:#e0e0e0;padding:10px 14px;font-size:13.5px;resize:none;outline:0;font-family:inherit;min-height:20px;max-height:120px}\
.ob-in:focus{border-color:rgba(255,102,0,.4)}\
.ob-in::placeholder{color:#555}\
.ob-send{width:38px;height:38px;border-radius:8px;background:linear-gradient(135deg,#ff6600,#f59e0b);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}\
.ob-send:disabled{opacity:.3;cursor:default}\
.ob-send svg{width:18px;height:18px;fill:#fff}\
.ob-stop{width:38px;height:38px;border-radius:8px;background:#dc2626;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}\
.ob-stop svg{width:16px;height:16px;fill:#fff}\
.ob-footer{display:flex;align-items:center;gap:6px;padding:6px 12px;font-size:11px;color:#555;border-top:1px solid #1a1a2e}\
.ob-welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;padding:20px;color:#888}\
.ob-welcome h3{color:#e0e0e0;margin:0 0 6px;font-size:17px}\
.ob-welcome p{font-size:13px;max-width:280px;margin:0 0 16px;line-height:1.5}\
.ob-sugg-list{display:flex;flex-direction:column;gap:6px;width:100%}\
.ob-sugg{padding:9px 14px;background:#181b23;border:1px solid #2a2a3e;border-radius:8px;cursor:pointer;text-align:left;color:#ccc;font-size:12.5px}\
.ob-sugg:hover{background:#1e1e2e;border-color:rgba(255,102,0,.3);color:#f59e0b}\
.ob-err{color:#ef4444;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:6px;padding:8px 12px;margin:6px 0;font-size:12px}\
.ob-user-badge{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;background:#1e1e2e;border-radius:10px;font-size:11px;color:#888}\
.ob-user-badge span{color:#60a5fa}\
.ob-ts{font-size:10px;color:#444;margin-top:2px}\
";
  document.head.appendChild(css);

  // ── Icons ──
  var ICO_BOT = '<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 012 2v1h4a3 3 0 013 3v8a3 3 0 01-3 3H6a3 3 0 01-3-3V8a3 3 0 013-3h4V4a2 2 0 012-2zm-3 9a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/></svg>';
  var ICO_SEND = '<svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICO_STOP = '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="#fff"/></svg>';

  // ── Mount ──
  var root = document.createElement("div");
  root.id = WIDGET_ID;
  document.body.appendChild(root);

  var drag = { active: false, ox: 0, oy: 0 };
  var abortCtrl = null;
  var msgCounter = Date.now();

  // Cached DOM references for streaming updates
  var currentBotBubble = null;
  var currentTypingEl = null;

  function fmtTime(ts) {
    if (!ts) return "";
    var d = new Date(ts);
    var h = d.getHours(); var m = d.getMinutes();
    return (h % 12 || 12) + ":" + (m<10?"0":"") + m + " " + (h>=12?"PM":"AM");
  }

  // ── Minimal Markdown ──
  function esc(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }
  function fmtMd(s) {
    if (!s) return "";
    s = esc(s);
    // Links: [text](url)
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    // Code blocks ```...```
    s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, function(_,l,c) { return "<pre><code>" + c.trim() + "</code></pre>"; });
    // Inline code `...`
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bold **...**
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic _..._
    s = s.replace(/\b_([^_]+)_\b/g, "<em>$1</em>");
    // Lists: lines starting with "- "
    s = s.replace(/(^|\n)- (.+)/g, "$1<li>$2</li>");
    s = s.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");
    // Collapse multiple <ul>
    s = s.replace(/<\/ul>\s*<ul>/g, "");
    // Line breaks
    s = s.replace(/\n/g, "<br/>");
    return s;
  }

  // ── Render position ──
  function applyPos() {
    // Reset classes first
    root.classList.remove("ob-maximized", "ob-fullscreen");

    if (state.mode === "maximized" || state.mode === "fullscreen") {
      // Cover the whole viewport as an overlay container
      root.style.cssText = "position:fixed;z-index:999999;left:0;top:0;right:0;bottom:0;width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;" +
        (state.mode === "fullscreen" ? "background:#0d0d12;" : "background:rgba(0,0,0,.35);backdrop-filter:blur(3px);");
      root.classList.add("ob-" + state.mode);
      return;
    }
    // Normal: floating corner/custom position
    var posStyle;
    if (state.posX != null && state.posY != null) {
      posStyle = "left:" + state.posX + "px;top:" + state.posY + "px;";
    } else {
      posStyle = "bottom:24px;right:24px;";
    }
    root.style.cssText = "position:fixed;z-index:999999;" + posStyle;
  }

  // ── Render FAB (closed state) ──
  function renderFab() {
    applyPos();
    root.innerHTML = '<button class="ob-fab" title="O11yBot">' + ICO_BOT + '<div class="ob-dot"></div></button>';
    root.querySelector(".ob-fab").onclick = function() { state.open = true; renderPanel(); };
  }

  // ── Render full panel ──
  function renderPanel() {
    applyPos();
    currentBotBubble = null;
    currentTypingEl = null;

    var msgsHtml = "";
    if (state.msgs.length === 0) {
      var suggs = [
        "List all Grafana dashboards",
        "List datasources",
        "Check Grafana health",
        "List folders"
      ];
      msgsHtml = '<div class="ob-welcome"><h3>Hey ' + esc(grafanaUser.name.split(" ")[0]) + '!</h3><p>Ask me about dashboards, metrics, logs, traces, or incidents.</p><div class="ob-sugg-list">';
      for (var si = 0; si < suggs.length; si++) {
        msgsHtml += '<button class="ob-sugg">' + esc(suggs[si]) + '</button>';
      }
      msgsHtml += '</div></div>';
    } else {
      for (var i = 0; i < state.msgs.length; i++) {
        var m = state.msgs[i];
        var isU = m.role === "user";
        var cls = isU ? "ob-msg ob-msg-u" : "ob-msg ob-msg-b";
        msgsHtml += '<div class="' + cls + '" data-mid="' + m.id + '">';
        msgsHtml += '<div class="ob-av">' + (isU ? esc(userInitial) : "O") + '</div>';
        msgsHtml += '<div class="ob-msg-wrap">';
        if (isU) {
          msgsHtml += '<div class="ob-bub">' + esc(m.content) + '</div>';
        } else {
          msgsHtml += '<div class="ob-bub">' + fmtMd(m.content || "") + '</div>';
          if (m.streaming) msgsHtml += '<div class="ob-typing"><span></span><span></span><span></span></div>';
          if (!m.streaming && (m.cost > 0 || m.tokens > 0)) {
            msgsHtml += '<div class="ob-meta">';
            if (m.tokens > 0) msgsHtml += '<span>' + m.tokens + ' tok</span>';
            if (m.cost > 0) msgsHtml += '<span class="ob-cost">$' + m.cost.toFixed(4) + '</span>';
            msgsHtml += '</div>';
          }
        }
        if (m.ts) msgsHtml += '<div class="ob-ts">' + fmtTime(m.ts) + '</div>';
        msgsHtml += '</div></div>';
      }
    }

    // Icons for window controls
    var ICO_CLEAR  = '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M5 6v14a2 2 0 002 2h10a2 2 0 002-2V6" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
    var ICO_MIN    = '<svg viewBox="0 0 24 24"><path d="M4 14h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
    var ICO_MAX    = '<svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
    var ICO_RESTORE = '<svg viewBox="0 0 24 24"><rect x="8" y="4" width="12" height="12" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/><rect x="4" y="8" width="12" height="12" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="#111217"/></svg>';
    var ICO_FULL   = '<svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg>';
    var ICO_FULL_EXIT = '<svg viewBox="0 0 24 24"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg>';
    var ICO_CLOSE  = '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';

    // Determine which buttons to show based on current mode
    var modeClass = state.mode === "maximized" ? "ob-maximized" : (state.mode === "fullscreen" ? "ob-fullscreen" : "");
    if (modeClass) root.classList.add(modeClass); else root.classList.remove("ob-maximized","ob-fullscreen");

    var maxBtnIcon = state.mode === "maximized" ? ICO_RESTORE : ICO_MAX;
    var maxBtnTitle = state.mode === "maximized" ? "Restore" : "Maximize";
    var fullBtnIcon = state.mode === "fullscreen" ? ICO_FULL_EXIT : ICO_FULL;
    var fullBtnTitle = state.mode === "fullscreen" ? "Exit fullscreen" : "Fullscreen";

    root.innerHTML =
      '<div class="ob-panel ' + modeClass + '">' +
        '<div class="ob-hdr" id="ob-hdr">' +
          '<div class="ob-hdr-icon">' + ICO_BOT + '</div>' +
          '<div style="flex:1"><div class="ob-title">O11yBot</div><div class="ob-sub">O11y Assistant \u2022 drag to move</div></div>' +
          '<div class="ob-acts">' +
            '<button class="ob-hbtn" id="ob-clear" title="Clear chat">' + ICO_CLEAR + '</button>' +
            '<button class="ob-hbtn" id="ob-min" title="Minimize">' + ICO_MIN + '</button>' +
            '<button class="ob-hbtn" id="ob-max" title="' + maxBtnTitle + '">' + maxBtnIcon + '</button>' +
            '<button class="ob-hbtn" id="ob-full" title="' + fullBtnTitle + '">' + fullBtnIcon + '</button>' +
            '<button class="ob-hbtn" id="ob-close" title="Close">' + ICO_CLOSE + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="ob-msgs" id="ob-msgs">' + msgsHtml + '</div>' +
        '<div class="ob-footer">' +
          '<div class="ob-user-badge"><span>\u25CF</span> ' + esc(grafanaUser.name) + '</div>' +
          '<span style="margin-left:auto">' + state.msgs.length + ' msgs</span>' +
        '</div>' +
        '<div class="ob-in-area"><div class="ob-in-row">' +
          '<textarea class="ob-in" id="ob-input" rows="1" placeholder="Ask about observability..."></textarea>' +
          '<button class="ob-send" id="ob-send">' + ICO_SEND + '</button>' +
        '</div></div>' +
      '</div>';

    wireEvents();
    scrollToBottom();
  }

  function wireEvents() {
    var hdr = document.getElementById("ob-hdr");
    if (hdr) hdr.onmousedown = startDrag;

    var closeBtn = document.getElementById("ob-close");
    if (closeBtn) closeBtn.onclick = function() {
      state.open = false;
      state.mode = "normal";  // reset on close
      saveState();
      renderFab();
    };

    var minBtn = document.getElementById("ob-min");
    if (minBtn) minBtn.onclick = function() {
      state.open = false;
      saveState();
      renderFab();
    };

    var maxBtn = document.getElementById("ob-max");
    if (maxBtn) maxBtn.onclick = function() {
      state.mode = state.mode === "maximized" ? "normal" : "maximized";
      saveState();
      renderPanel();
    };

    var fullBtn = document.getElementById("ob-full");
    if (fullBtn) fullBtn.onclick = function() {
      state.mode = state.mode === "fullscreen" ? "normal" : "fullscreen";
      saveState();
      renderPanel();
    };

    var clearBtn = document.getElementById("ob-clear");
    if (clearBtn) clearBtn.onclick = function() { state.msgs = []; saveState(); renderPanel(); };
    var inp = document.getElementById("ob-input");
    if (inp) {
      inp.onkeydown = function(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(inp.value); }
      };
      inp.focus();
    }
    var sendBtn = document.getElementById("ob-send");
    if (sendBtn) sendBtn.onclick = function() { send(document.getElementById("ob-input").value); };
    var suggs = root.querySelectorAll(".ob-sugg");
    for (var si = 0; si < suggs.length; si++) {
      suggs[si].onclick = function() { send(this.textContent); };
    }
  }

  function scrollToBottom() {
    var msgsEl = document.getElementById("ob-msgs");
    if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function startDrag(ev) {
    if (ev.target.tagName === "BUTTON" || ev.target.closest("button")) return;
    // Don't drag when maximized or fullscreen
    if (state.mode === "maximized" || state.mode === "fullscreen") return;
    var rect = root.getBoundingClientRect();
    drag = { active: true, ox: ev.clientX - rect.left, oy: ev.clientY - rect.top };
    document.onmousemove = function(ev2) {
      if (!drag.active) return;
      var nx = Math.max(0, Math.min(window.innerWidth - 100, ev2.clientX - drag.ox));
      var ny = Math.max(0, Math.min(window.innerHeight - 100, ev2.clientY - drag.oy));
      state.posX = nx; state.posY = ny;
      root.style.left = nx + "px"; root.style.top = ny + "px";
      root.style.right = ""; root.style.bottom = "";
    };
    document.onmouseup = function() {
      drag.active = false;
      document.onmousemove = null; document.onmouseup = null;
      saveState();
    };
  }

  // ── Append bot message directly (for streaming) ──
  function appendBotMessage(botMsg) {
    var msgsEl = document.getElementById("ob-msgs");
    if (!msgsEl) return;

    // Remove welcome screen if present
    var welcome = msgsEl.querySelector(".ob-welcome");
    if (welcome) welcome.remove();

    var div = document.createElement("div");
    div.className = "ob-msg ob-msg-b";
    div.dataset.mid = botMsg.id;
    div.innerHTML =
      '<div class="ob-av">O</div>' +
      '<div class="ob-msg-wrap">' +
        '<div class="ob-bub"></div>' +
        '<div class="ob-typing"><span></span><span></span><span></span></div>' +
        '<div class="ob-ts">' + fmtTime(botMsg.ts) + '</div>' +
      '</div>';
    msgsEl.appendChild(div);

    currentBotBubble = div.querySelector(".ob-bub");
    currentTypingEl = div.querySelector(".ob-typing");

    console.log("[O11yBot] Bot bubble created:", currentBotBubble);
    scrollToBottom();
  }

  function appendUserMessage(userMsg) {
    var msgsEl = document.getElementById("ob-msgs");
    if (!msgsEl) return;
    var welcome = msgsEl.querySelector(".ob-welcome");
    if (welcome) welcome.remove();

    var div = document.createElement("div");
    div.className = "ob-msg ob-msg-u";
    div.dataset.mid = userMsg.id;
    div.innerHTML =
      '<div class="ob-av">' + esc(userInitial) + '</div>' +
      '<div class="ob-msg-wrap">' +
        '<div class="ob-bub">' + esc(userMsg.content) + '</div>' +
        '<div class="ob-ts">' + fmtTime(userMsg.ts) + '</div>' +
      '</div>';
    msgsEl.appendChild(div);
    scrollToBottom();
  }

  // ── Send ──
  function send(text) {
    if (!text || !text.trim() || state.streaming) return;
    text = text.trim();
    var uid = ++msgCounter;
    var now = Date.now();
    var userMsg = { role: "user", content: text, id: "u" + uid, ts: now };
    var botMsg = { role: "bot", content: "", id: "b" + uid, ts: now, streaming: true, cost: 0, tokens: 0 };

    console.log("[O11yBot] send:", text);

    state.msgs.push(userMsg);
    state.msgs.push(botMsg);
    state.streaming = true;

    // Clear input + append messages directly (no full re-render)
    var inp = document.getElementById("ob-input");
    if (inp) inp.value = "";
    appendUserMessage(userMsg);
    appendBotMessage(botMsg);

    // Build messages array for API
    var allMsgs = [];
    for (var i = 0; i < state.msgs.length - 1; i++) {
      var m = state.msgs[i];
      allMsgs.push({ role: m.role === "user" ? "user" : "assistant", content: m.content });
    }

    abortCtrl = new AbortController();

    console.log("[O11yBot] POST", ORCHESTRATOR + "/api/v1/chat");

    fetch(ORCHESTRATOR + "/api/v1/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Grafana-User": grafanaUser.login,
        "X-Grafana-Org-Id": String(grafanaUser.orgId)
      },
      body: JSON.stringify({
        messages: allMsgs,
        system: "You are O11yBot, an assistant embedded in Grafana for " + grafanaUser.name + ". Help with observability. Be brief. Use code blocks for queries.",
        max_tokens: 4096, temperature: 0.2, stream: true
      }),
      signal: abortCtrl.signal
    }).then(function(resp) {
      console.log("[O11yBot] Response:", resp.status, resp.headers.get("content-type"));
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      if (!resp.body) throw new Error("No response body");

      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      var acc = "";

      function read() {
        return reader.read().then(function(r) {
          if (r.done) {
            console.log("[O11yBot] Stream done. Total content length:", acc.length);
            finish();
            return;
          }
          buf += decoder.decode(r.value, { stream: true });
          // Normalize CRLF -> LF so the frame separator is always \n\n
          buf = buf.replace(/\r\n/g, "\n");
          var sep;
          while ((sep = buf.indexOf("\n\n")) !== -1) {
            var frame = buf.slice(0, sep);
            buf = buf.slice(sep + 2);
            var lines = frame.split("\n");
            for (var li = 0; li < lines.length; li++) {
              if (lines[li].indexOf("data: ") !== 0) continue;
              var js = lines[li].slice(6);
              if (js === "[DONE]") continue;
              try {
                var ev = JSON.parse(js);
                if (ev.type === "text") {
                  acc += ev.delta;
                  botMsg.content = acc;
                  if (currentBotBubble) currentBotBubble.innerHTML = fmtMd(acc);
                  scrollToBottom();
                } else if (ev.type === "usage") {
                  botMsg.cost = ev.costUsd || 0;
                  botMsg.tokens = (ev.usage||{}).totalTokens || 0;
                } else if (ev.type === "tool_start") {
                  console.log("[O11yBot] tool_start:", ev.name, ev.input);
                } else if (ev.type === "tool_result") {
                  console.log("[O11yBot] tool_result:", ev.durationMs + "ms", ev.error || "OK");
                } else if (ev.type === "error") {
                  acc += "\n\n**Error:** " + ev.message;
                  botMsg.content = acc;
                  if (currentBotBubble) currentBotBubble.innerHTML = fmtMd(acc);
                }
              } catch(e) { console.warn("[O11yBot] parse err:", e, js); }
            }
          }
          return read();
        });
      }
      return read();
    }).catch(function(err) {
      console.error("[O11yBot] Fetch error:", err);
      if (err.name !== "AbortError") {
        botMsg.content = "Error: " + err.message;
        if (currentBotBubble) currentBotBubble.innerHTML = '<div class="ob-err">' + esc(err.message) + '</div>';
      }
      finish();
    });

    function finish() {
      botMsg.streaming = false;
      state.streaming = false;
      if (currentTypingEl) currentTypingEl.remove();
      currentTypingEl = null;
      saveState();

      // Add token/cost meta if available
      if (currentBotBubble && (botMsg.cost > 0 || botMsg.tokens > 0)) {
        var wrap = currentBotBubble.parentElement;
        var meta = document.createElement("div");
        meta.className = "ob-meta";
        var metaHtml = "";
        if (botMsg.tokens > 0) metaHtml += '<span>' + botMsg.tokens + ' tok</span>';
        if (botMsg.cost > 0) metaHtml += '<span class="ob-cost">$' + botMsg.cost.toFixed(4) + '</span>';
        meta.innerHTML = metaHtml;
        wrap.insertBefore(meta, wrap.querySelector(".ob-ts"));
      }
    }
  }

  // ── Keyboard shortcuts ──
  document.addEventListener("keydown", function(ev) {
    if (ev.key === "Escape" && state.open && (state.mode === "fullscreen" || state.mode === "maximized")) {
      state.mode = "normal";
      saveState();
      renderPanel();
    }
  });

  // ── Init ──
  if (state.open) renderPanel(); else renderFab();
  console.log("%c[O11yBot] v" + WIDGET_VERSION + " ready. User: " + grafanaUser.login, "color:#22c55e;font-weight:bold;");
})();
