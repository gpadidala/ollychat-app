/**
 * O11yBot — Floating Grafana Chatbot Widget v1.5.0
 *
 * Features:
 * - Multi-session history (VSCode-style) with per-user isolation
 * - Grafana RBAC enforcement (X-Grafana-Role header)
 * - Restore/continue previous conversations
 * - Drag, resize, minimize, maximize, fullscreen
 */
(function() {
  "use strict";
  var WIDGET_VERSION = "1.8.0";
  var ORCHESTRATOR = "http://localhost:8000";
  var WIDGET_ID = "o11ybot-root";

  if (document.getElementById(WIDGET_ID)) {
    console.log("[O11yBot] Already loaded, skipping");
    return;
  }

  console.log("%c[O11yBot] v" + WIDGET_VERSION + " initializing...", "color:#f59e0b;font-weight:bold;font-size:14px;");

  // ═══════════════════════════════════════════════════════════
  // Grafana user identity + RBAC role
  // ═══════════════════════════════════════════════════════════
  var grafanaUser = { login: "anonymous", name: "User", orgId: 1, role: "Viewer" };
  try {
    if (window.grafanaBootData && window.grafanaBootData.user) {
      var gu = window.grafanaBootData.user;
      grafanaUser.login = gu.login || gu.email || "anonymous";
      grafanaUser.name = gu.name || gu.login || "User";
      grafanaUser.orgId = gu.orgId || 1;
      // Grafana role: "Viewer" | "Editor" | "Admin" | "Grafana Admin"
      grafanaUser.role = gu.orgRole || gu.role || "Viewer";
    }
  } catch(e) { console.warn("[O11yBot] Could not read grafanaBootData:", e); }

  console.log("[O11yBot] User:", grafanaUser);

  var STORE_KEY = "o11ybot-" + grafanaUser.login;
  var userInitial = (grafanaUser.name || "U").charAt(0).toUpperCase();

  // ═══════════════════════════════════════════════════════════
  // State: multi-session history (like VSCode chat)
  // ═══════════════════════════════════════════════════════════
  var state = (function() {
    try {
      var s = localStorage.getItem(STORE_KEY);
      var parsed = s ? JSON.parse(s) : {};
      // ── Migrate from old flat-msgs format ──
      if (parsed.msgs && !parsed.sessions) {
        parsed.sessions = parsed.msgs.length > 0
          ? [{ id: "migrated-" + Date.now(), title: "Previous session", msgs: parsed.msgs, createdAt: Date.now(), updatedAt: Date.now() }]
          : [];
        delete parsed.msgs;
      }
      return parsed;
    } catch(e) { return {}; }
  })();

  state.sessions = state.sessions || [];
  state.activeSessionId = state.activeSessionId || null;
  state.open = false;       // re-opened by user each page load
  state.view = "chat";      // "chat" | "history"
  state.streaming = false;
  state.showShortcuts = false;
  state.historySearch = "";     // current search filter
  state.starredIds = state.starredIds || [];  // pinned/favorite sessions
  state.mode = state.mode || "normal";
  state.posX = state.posX != null ? state.posX : null;
  state.posY = state.posY != null ? state.posY : null;

  function saveState() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({
        sessions: state.sessions.slice(-50),  // cap at 50 sessions
        activeSessionId: state.activeSessionId,
        starredIds: state.starredIds || [],
        mode: state.mode,
        posX: state.posX, posY: state.posY,
      }));
    } catch(e) {}
  }

  function uuid() { return "s" + Date.now() + "-" + Math.random().toString(36).slice(2, 8); }

  function getActiveSession() {
    if (!state.activeSessionId) return null;
    return state.sessions.find(function(s) { return s.id === state.activeSessionId; }) || null;
  }

  function newSession() {
    var s = { id: uuid(), title: "New chat", msgs: [], createdAt: Date.now(), updatedAt: Date.now() };
    state.sessions.unshift(s);
    state.activeSessionId = s.id;
    saveState();
    return s;
  }

  function deleteSession(id) {
    state.sessions = state.sessions.filter(function(s) { return s.id !== id; });
    if (state.activeSessionId === id) state.activeSessionId = null;
    saveState();
  }

  function selectSession(id) {
    state.activeSessionId = id;
    state.view = "chat";
    saveState();
  }

  // Auto-title a session from its first user message
  function autoTitle(session) {
    if (!session || !session.msgs || session.msgs.length === 0) return "New chat";
    var firstUser = session.msgs.find(function(m) { return m.role === "user"; });
    if (!firstUser) return "New chat";
    var t = firstUser.content.slice(0, 50).trim();
    return t + (firstUser.content.length > 50 ? "…" : "");
  }

  // ═══════════════════════════════════════════════════════════
  // CSS
  // ═══════════════════════════════════════════════════════════
  var css = document.createElement("style");
  css.textContent = "\
#o11ybot-root{position:fixed;z-index:999999;font-family:Inter,-apple-system,sans-serif;font-size:14px;color:#e0e0e0}\
.ob-fab{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#ff6600,#f59e0b);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(255,102,0,.4),0 2px 8px rgba(0,0,0,.3);transition:transform .2s;position:relative}\
.ob-fab:hover{transform:scale(1.1)}\
.ob-fab svg{width:28px;height:28px;fill:#fff}\
.ob-dot{position:absolute;top:-2px;right:-2px;width:14px;height:14px;border-radius:50%;background:#22c55e;border:2px solid #111}\
.ob-panel{width:460px;height:620px;background:#111217;border:1px solid #2a2a3e;border-radius:12px;display:flex;flex-direction:column;box-shadow:0 12px 48px rgba(0,0,0,.5);overflow:hidden;resize:both;min-width:360px;min-height:420px;max-width:90vw;max-height:85vh}\
.ob-panel.ob-maximized{width:75vw!important;height:85vh!important;resize:none}\
.ob-panel.ob-fullscreen{width:100vw!important;height:100vh!important;border-radius:0;resize:none;border:none}\
#o11ybot-root.ob-maximized,#o11ybot-root.ob-fullscreen{display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.35);backdrop-filter:blur(3px)}\
#o11ybot-root.ob-fullscreen{background:#0d0d12}\
.ob-hdr{display:flex;align-items:center;gap:10px;padding:12px 16px;background:linear-gradient(135deg,#1a1025,#111217);border-bottom:1px solid #2a2a3e;cursor:grab;user-select:none}\
.ob-hdr:active{cursor:grabbing}\
.ob-hdr-icon{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#ff6600,#f59e0b);display:flex;align-items:center;justify-content:center;flex-shrink:0}\
.ob-hdr-icon svg{width:18px;height:18px;fill:#fff}\
.ob-title{font-weight:600;font-size:15px}\
.ob-sub{font-size:11px;color:#888;margin-top:1px}\
.ob-acts{display:flex;gap:4px}\
.ob-hbtn{width:28px;height:28px;border-radius:6px;background:0 0;border:1px solid transparent;color:#888;cursor:pointer;display:flex;align-items:center;justify-content:center}\
.ob-hbtn:hover{background:rgba(255,255,255,.06);color:#ccc}\
.ob-hbtn svg{width:16px;height:16px;fill:currentColor}\
.ob-tabs{display:flex;border-bottom:1px solid #2a2a3e;background:#0d0d12}\
.ob-tab{flex:1;padding:10px 14px;cursor:pointer;color:#888;font-size:12.5px;font-weight:500;text-align:center;border-bottom:2px solid transparent;transition:all .15s;display:flex;align-items:center;justify-content:center;gap:6px}\
.ob-tab:hover{color:#ccc;background:rgba(255,255,255,.03)}\
.ob-tab.active{color:#f59e0b;border-bottom-color:#f59e0b;background:#181b23}\
.ob-tab-badge{background:#2a2a3e;color:#888;border-radius:10px;padding:1px 7px;font-size:10px;font-weight:600}\
.ob-tab.active .ob-tab-badge{background:#ff660033;color:#f59e0b}\
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
.ob-bub a:hover{color:#93bbfc}\
.ob-bub strong{color:#fff}\
.ob-bub em{color:#aaa;font-style:italic}\
.ob-bub ul{margin:8px 0;padding-left:20px}\
.ob-bub li{margin:4px 0}\
.ob-bub sup{font-size:9px;color:#555}\
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
.ob-user-badge{display:inline-flex;align-items:center;gap:4px;padding:1px 8px;background:#1e1e2e;border-radius:10px;font-size:11px;color:#888}\
.ob-user-badge span{color:#60a5fa}\
.ob-role-badge{padding:1px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase}\
.ob-role-viewer{background:rgba(96,165,250,.2);color:#60a5fa}\
.ob-role-editor{background:rgba(34,197,94,.2);color:#22c55e}\
.ob-role-admin{background:rgba(239,68,68,.2);color:#ef4444}\
.ob-kbd-btn{background:transparent;border:1px solid #2a2a3e;color:#888;padding:2px 8px;border-radius:10px;font-size:10px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;font-family:inherit}\
.ob-kbd-btn:hover{background:rgba(255,102,0,.1);border-color:rgba(255,102,0,.4);color:#f59e0b}\
.ob-kbd-btn svg{width:11px;height:11px;fill:currentColor}\
.ob-shortcuts-overlay{position:absolute;inset:0;background:rgba(0,0,0,.75);backdrop-filter:blur(4px);z-index:10;display:flex;align-items:center;justify-content:center;animation:ob-fadein .15s ease}\
@keyframes ob-fadein{from{opacity:0}to{opacity:1}}\
.ob-shortcuts-modal{background:#111217;border:1px solid #2a2a3e;border-radius:12px;width:92%;max-width:420px;max-height:85%;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.6)}\
.ob-shortcuts-hdr{padding:14px 18px;border-bottom:1px solid #2a2a3e;display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,#1a1025,#111217);border-radius:12px 12px 0 0}\
.ob-shortcuts-hdr h3{margin:0;font-size:14px;color:#f59e0b;font-weight:600;display:flex;align-items:center;gap:8px}\
.ob-shortcuts-close{background:transparent;border:none;color:#888;cursor:pointer;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center}\
.ob-shortcuts-close:hover{background:rgba(255,255,255,.06);color:#ccc}\
.ob-shortcuts-body{padding:10px 18px}\
.ob-shortcuts-group{margin-bottom:14px}\
.ob-shortcuts-group h4{margin:8px 0 6px;font-size:10.5px;color:#888;text-transform:uppercase;font-weight:600;letter-spacing:0.8px}\
.ob-shortcut{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04)}\
.ob-shortcut:last-child{border:none}\
.ob-shortcut-label{font-size:12px;color:#ccc}\
.ob-shortcut-keys{display:flex;gap:3px}\
.ob-shortcut-kbd{background:#0d0d12;border:1px solid #2a2a3e;border-bottom-width:2px;border-radius:4px;padding:2px 6px;font-family:\"JetBrains Mono\",monospace;font-size:10.5px;color:#f59e0b;min-width:20px;text-align:center}\
.ob-welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;text-align:center;padding:20px;color:#888}\
.ob-welcome h3{color:#e0e0e0;margin:0 0 6px;font-size:17px}\
.ob-welcome p{font-size:13px;max-width:280px;margin:0 0 16px;line-height:1.5}\
.ob-sugg-list{display:flex;flex-direction:column;gap:6px;width:100%;max-width:360px}\
.ob-sugg{padding:9px 14px;background:#181b23;border:1px solid #2a2a3e;border-radius:8px;cursor:pointer;text-align:left;color:#ccc;font-size:12.5px}\
.ob-sugg:hover{background:#1e1e2e;border-color:rgba(255,102,0,.3);color:#f59e0b}\
.ob-quick-actions{width:100%;max-width:400px}\
.ob-qa-group{margin-bottom:12px}\
.ob-qa-title{font-size:10.5px;color:#888;text-transform:uppercase;font-weight:600;letter-spacing:0.6px;margin:6px 4px 6px;text-align:left}\
.ob-qa-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}\
.ob-qa-btn{padding:8px 10px;background:#181b23;border:1px solid #2a2a3e;border-radius:7px;cursor:pointer;color:#ccc;font-size:12px;display:flex;align-items:center;gap:6px;text-align:left;transition:all .15s;line-height:1.2}\
.ob-qa-btn:hover{background:#1e1e2e;border-color:rgba(255,102,0,.4);color:#f59e0b;transform:translateY(-1px)}\
.ob-qa-btn .ob-qa-icon{font-size:14px;flex-shrink:0}\
.ob-ts{font-size:10px;color:#444;margin-top:2px}\
.ob-history-wrap{flex:1;display:flex;flex-direction:column;overflow:hidden;background:#0d0d12}\
.ob-history-toolbar{display:flex;gap:8px;padding:10px 12px;border-bottom:1px solid #1a1a2e;background:#111217}\
.ob-history-search{flex:1;background:#181b23;border:1px solid #2a2a3e;border-radius:6px;padding:7px 10px 7px 32px;color:#e0e0e0;font-size:12.5px;font-family:inherit;outline:0;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:10px center}\
.ob-history-search:focus{border-color:rgba(255,102,0,.4)}\
.ob-new-chat-btn{padding:7px 10px;background:linear-gradient(135deg,#ff6600,#f59e0b);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:12.5px;display:inline-flex;align-items:center;justify-content:center;gap:5px;flex-shrink:0;white-space:nowrap;height:32px}\
.ob-new-chat-btn:hover{opacity:.9}\
.ob-new-chat-btn svg{width:14px;height:14px;fill:currentColor}\
.ob-history-list{flex:1;overflow-y:auto;padding:6px 10px 12px}\
.ob-history-list::-webkit-scrollbar{width:5px}\
.ob-history-list::-webkit-scrollbar-thumb{background:#333;border-radius:3px}\
.ob-hi-group-title{font-size:10px;color:#666;text-transform:uppercase;font-weight:700;letter-spacing:0.8px;padding:12px 4px 6px;display:flex;align-items:center;gap:6px}\
.ob-hi-group-count{background:#1e1e2e;color:#888;padding:0 6px;border-radius:8px;font-size:9.5px;font-weight:600}\
.ob-history-item{padding:10px 12px;margin:4px 0;border-radius:8px;cursor:pointer;background:#181b23;border:1px solid #2a2a3e;position:relative;transition:all .15s;display:flex;gap:10px;align-items:flex-start}\
.ob-history-item:hover{background:#1e1e2e;border-color:rgba(255,102,0,.3);transform:translateX(2px)}\
.ob-history-item.active{background:linear-gradient(135deg,#1a1025,#181b23);border-color:#f59e0b}\
.ob-history-item.active::before{content:'';position:absolute;left:-10px;top:10px;bottom:10px;width:3px;background:#f59e0b;border-radius:2px}\
.ob-hi-icon{font-size:17px;flex-shrink:0;padding-top:1px}\
.ob-hi-body{flex:1;min-width:0}\
.ob-hi-title{font-size:13px;color:#e0e0e0;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-right:40px}\
.ob-history-item.active .ob-hi-title{color:#f59e0b}\
.ob-hi-preview{font-size:11.5px;color:#777;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.3;padding-right:40px}\
.ob-hi-meta{display:flex;gap:8px;margin-top:5px;font-size:10px;color:#666;align-items:center}\
.ob-hi-msgs{background:rgba(255,102,0,.12);color:#f59e0b;padding:1px 7px;border-radius:8px;font-weight:600}\
.ob-hi-actions{position:absolute;top:8px;right:8px;display:flex;gap:2px;opacity:0;transition:opacity .15s}\
.ob-history-item:hover .ob-hi-actions,.ob-history-item.active .ob-hi-actions{opacity:1}\
.ob-hi-action{width:22px;height:22px;border-radius:4px;background:rgba(13,13,18,.8);border:none;color:#666;cursor:pointer;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px)}\
.ob-hi-action svg{width:12px;height:12px;fill:currentColor}\
.ob-hi-action:hover{color:#ccc;background:rgba(30,30,46,.9)}\
.ob-hi-action.ob-hi-del:hover{background:rgba(239,68,68,.3);color:#ef4444}\
.ob-hi-action.ob-hi-star.starred{color:#f59e0b}\
.ob-hi-action.ob-hi-star:hover{color:#f59e0b;background:rgba(245,158,11,.2)}\
.ob-hi-empty{padding:50px 20px;text-align:center;color:#666;font-size:13px}\
.ob-hi-empty .ob-hi-empty-icon{font-size:48px;margin-bottom:12px;opacity:0.3}\
.ob-hi-empty p{margin:8px 0}\
.ob-hi-empty-cta{margin-top:16px;padding:8px 16px;background:linear-gradient(135deg,#ff6600,#f59e0b);color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px}\
.ob-hi-no-results{padding:30px 20px;text-align:center;color:#666;font-size:13px}\
";
  document.head.appendChild(css);

  // ═══════════════════════════════════════════════════════════
  // Icons
  // ═══════════════════════════════════════════════════════════
  var ICO_BOT = '<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 012 2v1h4a3 3 0 013 3v8a3 3 0 01-3 3H6a3 3 0 01-3-3V8a3 3 0 013-3h4V4a2 2 0 012-2zm-3 9a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/></svg>';
  var ICO_SEND = '<svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICO_STOP = '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="#fff"/></svg>';
  var ICO_NEW = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var ICO_TRASH = '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M5 6v14a2 2 0 002 2h10a2 2 0 002-2V6" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
  var ICO_CLOSE = '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var ICO_MIN = '<svg viewBox="0 0 24 24"><path d="M4 14h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var ICO_MAX = '<svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>';
  var ICO_FULL = '<svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg>';

  // ═══════════════════════════════════════════════════════════
  // Mount
  // ═══════════════════════════════════════════════════════════
  var root = document.createElement("div");
  root.id = WIDGET_ID;
  document.body.appendChild(root);

  var drag = { active: false, ox: 0, oy: 0 };
  var abortCtrl = null;
  var currentBotBubble = null;
  var currentTypingEl = null;

  function fmtTime(ts) {
    if (!ts) return "";
    var d = new Date(ts);
    var h = d.getHours(); var m = d.getMinutes();
    return (h % 12 || 12) + ":" + (m<10?"0":"") + m + " " + (h>=12?"PM":"AM");
  }
  function fmtRelative(ts) {
    if (!ts) return "";
    var s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s/60) + "m ago";
    if (s < 86400) return Math.floor(s/3600) + "h ago";
    var d = Math.floor(s/86400);
    if (d === 1) return "yesterday";
    if (d < 7) return d + "d ago";
    return new Date(ts).toLocaleDateString();
  }

  function esc(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
  function fmtMd(s) {
    if (!s) return "";
    s = esc(s);
    // Links
    s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    // Code blocks
    s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, function(_,l,c) { return "<pre><code>" + c.trim() + "</code></pre>"; });
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|\s)_([^_\s][^_]*?)_(\s|$|\.|,|\))/g, "$1<em>$2</em>$3");
    // <sup>...</sup> pass-through (we already escaped < to &lt;)
    s = s.replace(/&lt;sup&gt;/g, "<sup>").replace(/&lt;\/sup&gt;/g, "</sup>");
    // Lists
    s = s.replace(/(^|\n)- (.+)/g, "$1<li>$2</li>");
    s = s.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");
    s = s.replace(/<\/ul>\s*<ul>/g, "");
    s = s.replace(/\n/g, "<br/>");
    return s;
  }

  function applyPos() {
    root.classList.remove("ob-maximized", "ob-fullscreen");
    if (state.mode === "maximized" || state.mode === "fullscreen") {
      root.style.cssText = "position:fixed;z-index:999999;left:0;top:0;right:0;bottom:0;width:100vw;height:100vh;" +
        (state.mode === "fullscreen" ? "background:#0d0d12;" : "background:rgba(0,0,0,.35);backdrop-filter:blur(3px);");
      root.classList.add("ob-" + state.mode);
      return;
    }
    var posStyle = (state.posX != null && state.posY != null)
      ? "left:" + state.posX + "px;top:" + state.posY + "px;"
      : "bottom:24px;right:24px;";
    root.style.cssText = "position:fixed;z-index:999999;" + posStyle;
  }

  // ═══════════════════════════════════════════════════════════
  // Render: FAB (closed state)
  // ═══════════════════════════════════════════════════════════
  function renderFab() {
    applyPos();
    root.innerHTML = '<button class="ob-fab" title="O11yBot (drag to move, click to chat)">' + ICO_BOT + '<div class="ob-dot"></div></button>';
    var fab = root.querySelector(".ob-fab");

    // Click to open — but only if not dragged
    var dragStarted = false;
    fab.addEventListener("mousedown", function(ev) {
      dragStarted = false;
      var startX = ev.clientX, startY = ev.clientY;
      var rect = root.getBoundingClientRect();
      var ox = ev.clientX - rect.left, oy = ev.clientY - rect.top;

      var onMove = function(e2) {
        if (!dragStarted && (Math.abs(e2.clientX - startX) > 3 || Math.abs(e2.clientY - startY) > 3)) {
          dragStarted = true;
          document.body.style.userSelect = "none";
        }
        if (dragStarted) {
          var nx = Math.max(0, Math.min(window.innerWidth - 60, e2.clientX - ox));
          var ny = Math.max(0, Math.min(window.innerHeight - 60, e2.clientY - oy));
          state.posX = nx; state.posY = ny;
          root.style.left = nx + "px"; root.style.top = ny + "px";
          root.style.right = "auto"; root.style.bottom = "auto";
        }
      };
      var onUp = function() {
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (dragStarted) saveState();
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    fab.onclick = function() {
      if (dragStarted) return;  // don't open if user dragged
      state.open = true;
      renderPanel();
    };
  }

  // ═══════════════════════════════════════════════════════════
  // Render: Chat tab (current active session)
  // ═══════════════════════════════════════════════════════════
  function renderChatTab() {
    currentBotBubble = null;
    currentTypingEl = null;
    var session = getActiveSession();
    var msgs = session ? session.msgs : [];

    if (msgs.length === 0) {
      // Grafana Quick Actions — one-click common queries
      var quickActions = [
        {
          title: "📊 Dashboards",
          actions: [
            { icon: "📋", label: "List all", q: "list all Grafana dashboards" },
            { icon: "🔍", label: "Search…", q: "search dashboards " },
            { icon: "📁", label: "Folders", q: "list all folders" },
            { icon: "⭐", label: "Starred", q: "list starred dashboards" },
          ],
        },
        {
          title: "🔔 Alerts",
          actions: [
            { icon: "🔴", label: "Firing", q: "show firing alerts" },
            { icon: "📝", label: "Rules", q: "list all alert rules" },
          ],
        },
        {
          title: "📡 Datasources",
          actions: [
            { icon: "📋", label: "List all", q: "list datasources" },
            { icon: "💓", label: "Health", q: "check grafana health" },
          ],
        },
        {
          title: "🏷️ By Category",
          actions: [
            { icon: "☸️", label: "AKS / K8s", q: "list AKS dashboards" },
            { icon: "☁️", label: "Azure", q: "list Azure dashboards" },
            { icon: "🗄️", label: "Database", q: "list database dashboards" },
            { icon: "🛡️", label: "Security", q: "list security dashboards" },
            { icon: "📊", label: "Loki", q: "list Loki dashboards" },
            { icon: "📈", label: "Mimir", q: "list Mimir dashboards" },
            { icon: "🔗", label: "Tempo", q: "list Tempo dashboards" },
            { icon: "🎯", label: "SLO", q: "list SLO dashboards" },
          ],
        },
      ];

      var welcome = '<div class="ob-welcome">';
      welcome += '<h3>Hey ' + esc(grafanaUser.name.split(" ")[0]) + '! 👋</h3>';
      welcome += '<p>One-click actions — or type your own question:</p>';
      welcome += '<div class="ob-quick-actions">';
      for (var gi = 0; gi < quickActions.length; gi++) {
        var g = quickActions[gi];
        welcome += '<div class="ob-qa-group">';
        welcome += '<div class="ob-qa-title">' + g.title + '</div>';
        welcome += '<div class="ob-qa-grid">';
        for (var ai = 0; ai < g.actions.length; ai++) {
          var a = g.actions[ai];
          welcome += '<button class="ob-qa-btn" data-q="' + esc(a.q) + '">';
          welcome += '<span class="ob-qa-icon">' + a.icon + '</span>';
          welcome += '<span>' + esc(a.label) + '</span>';
          welcome += '</button>';
        }
        welcome += '</div></div>';
      }
      welcome += '</div></div>';
      return '<div class="ob-msgs" id="ob-msgs">' + welcome + '</div>';
    }

    var html = '<div class="ob-msgs" id="ob-msgs">';
    var lastDate = "";
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      var isU = m.role === "user";
      var cls = isU ? "ob-msg ob-msg-u" : "ob-msg ob-msg-b";
      html += '<div class="' + cls + '" data-mid="' + m.id + '">';
      html += '<div class="ob-av">' + (isU ? esc(userInitial) : "O") + '</div>';
      html += '<div class="ob-msg-wrap">';
      if (isU) {
        html += '<div class="ob-bub">' + esc(m.content) + '</div>';
      } else {
        html += '<div class="ob-bub">' + fmtMd(m.content || "") + '</div>';
        if (!m.streaming && (m.cost > 0 || m.tokens > 0)) {
          html += '<div class="ob-meta">';
          if (m.tokens > 0) html += '<span>' + m.tokens + ' tok</span>';
          if (m.cost > 0) html += '<span class="ob-cost">$' + m.cost.toFixed(4) + '</span>';
          html += '</div>';
        }
      }
      if (m.ts) html += '<div class="ob-ts">' + fmtTime(m.ts) + '</div>';
      html += '</div></div>';
    }
    html += '<div id="ob-end"></div></div>';
    return html;
  }

  // ═══════════════════════════════════════════════════════════
  // Session icon from content (infer from first user message)
  // ═══════════════════════════════════════════════════════════
  function sessionIcon(session) {
    if (!session || !session.msgs || !session.msgs.length) return "💬";
    var firstUser = session.msgs.find(function(m) { return m.role === "user"; });
    if (!firstUser) return "💬";
    var q = firstUser.content.toLowerCase();
    if (/\bhelp|capabilit|what can|how can you/.test(q)) return "💡";
    if (/\balert|firing/.test(q)) return "🔔";
    if (/\bdatasource|data source/.test(q)) return "📡";
    if (/\bfolder/.test(q)) return "📁";
    if (/\bhealth|version|status/.test(q)) return "💓";
    if (/\buser\b/.test(q)) return "👥";
    if (/\bsearch\b/.test(q)) return "🔍";
    if (/\bpromql|rate\(|query/.test(q)) return "📈";
    if (/\blogql|loki|log/.test(q)) return "📝";
    if (/\btrace|tempo/.test(q)) return "🔗";
    if (/\baks|kubernetes|k8s/.test(q)) return "☸️";
    if (/\bazure|gcp|aws|oci/.test(q)) return "☁️";
    if (/\bsecurity|pci|hipaa|gdpr/.test(q)) return "🛡️";
    if (/\bdashboard|dash|board/.test(q)) return "📊";
    if (/\bslo|error budget|red\b/.test(q)) return "🎯";
    if (/\bincident|outage|down|slow/.test(q)) return "🚨";
    return "💬";
  }

  function sessionPreview(session) {
    if (!session || !session.msgs || !session.msgs.length) return "";
    // Show the last assistant message as preview
    for (var i = session.msgs.length - 1; i >= 0; i--) {
      if (session.msgs[i].role !== "user") {
        var preview = (session.msgs[i].content || "").replace(/\s+/g, " ").replace(/[*_`#>]/g, "");
        return preview.slice(0, 80);
      }
    }
    // Fallback to first user message
    return (session.msgs[0].content || "").slice(0, 80);
  }

  function groupByDate(sessions) {
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    var weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 7);

    var groups = { "Starred": [], "Today": [], "Yesterday": [], "This week": [], "Earlier": [] };
    for (var i = 0; i < sessions.length; i++) {
      var s = sessions[i];
      if ((state.starredIds || []).indexOf(s.id) >= 0) {
        groups["Starred"].push(s);
        continue;
      }
      var t = new Date(s.updatedAt);
      if (t >= today) groups["Today"].push(s);
      else if (t >= yesterday) groups["Yesterday"].push(s);
      else if (t >= weekAgo) groups["This week"].push(s);
      else groups["Earlier"].push(s);
    }
    return groups;
  }

  // ═══════════════════════════════════════════════════════════
  // Render: History tab (advanced, user-friendly)
  // ═══════════════════════════════════════════════════════════
  function renderHistoryTab() {
    var searchIconSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>';
    var plusSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
    var starSvg = '<svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';

    var html = '<div class="ob-history-wrap">';

    // Toolbar: search + new chat
    html += '<div class="ob-history-toolbar">';
    html += '<input type="text" class="ob-history-search" id="ob-history-search" placeholder="Search chats..." value="' + esc(state.historySearch || "") + '"/>';
    html += '<button class="ob-new-chat-btn" id="ob-new-chat" title="New chat (⌘N)">' + plusSvg + ' New</button>';
    html += '</div>';

    html += '<div class="ob-history-list">';

    if (state.sessions.length === 0) {
      html += '<div class="ob-hi-empty">';
      html += '<div class="ob-hi-empty-icon">💭</div>';
      html += '<p style="color:#aaa;font-weight:600">No chats yet</p>';
      html += '<p>Your conversations will appear here.</p>';
      html += '<button class="ob-hi-empty-cta" id="ob-new-chat-empty">Start a new chat</button>';
      html += '</div></div></div>';
      return html;
    }

    // Filter by search
    var search = (state.historySearch || "").toLowerCase().trim();
    var filtered = state.sessions;
    if (search) {
      filtered = state.sessions.filter(function(s) {
        if ((s.title || "").toLowerCase().indexOf(search) >= 0) return true;
        // Search within messages
        for (var i = 0; i < s.msgs.length; i++) {
          if ((s.msgs[i].content || "").toLowerCase().indexOf(search) >= 0) return true;
        }
        return false;
      });
    }

    if (filtered.length === 0) {
      html += '<div class="ob-hi-no-results">';
      html += '<p>🔍 No chats match "' + esc(search) + '"</p>';
      html += '</div></div></div>';
      return html;
    }

    // Sort by updatedAt desc
    var sorted = filtered.slice().sort(function(a, b) { return b.updatedAt - a.updatedAt; });

    // Group by date (or search = flat list)
    var groups = search ? { "Results": sorted } : groupByDate(sorted);

    var groupOrder = ["Starred", "Today", "Yesterday", "This week", "Earlier", "Results"];
    for (var gi = 0; gi < groupOrder.length; gi++) {
      var groupName = groupOrder[gi];
      var groupItems = groups[groupName] || [];
      if (groupItems.length === 0) continue;

      html += '<div class="ob-hi-group-title">';
      if (groupName === "Starred") html += '⭐ ';
      html += groupName + ' <span class="ob-hi-group-count">' + groupItems.length + '</span></div>';

      for (var i = 0; i < groupItems.length; i++) {
        var s = groupItems[i];
        var title = s.title || autoTitle(s);
        var active = s.id === state.activeSessionId ? "active" : "";
        var starred = (state.starredIds || []).indexOf(s.id) >= 0;
        var icon = sessionIcon(s);
        var preview = sessionPreview(s);

        html += '<div class="ob-history-item ' + active + '" data-sid="' + s.id + '">';
        html += '<div class="ob-hi-icon">' + icon + '</div>';
        html += '<div class="ob-hi-body">';
        html += '<div class="ob-hi-title">' + esc(title) + '</div>';
        if (preview) {
          html += '<div class="ob-hi-preview">' + esc(preview) + '</div>';
        }
        html += '<div class="ob-hi-meta">';
        html += '<span class="ob-hi-msgs">' + s.msgs.length + ' msg' + (s.msgs.length !== 1 ? 's' : '') + '</span>';
        html += '<span>' + fmtRelative(s.updatedAt) + '</span>';
        html += '</div>';
        html += '</div>';

        html += '<div class="ob-hi-actions">';
        html += '<button class="ob-hi-action ob-hi-star ' + (starred ? 'starred' : '') + '" data-star="' + s.id + '" title="' + (starred ? 'Unstar' : 'Star') + '">' + starSvg + '</button>';
        html += '<button class="ob-hi-action ob-hi-del" data-del="' + s.id + '" title="Delete">' + ICO_TRASH + '</button>';
        html += '</div>';

        html += '</div>';
      }
    }

    html += '</div></div>';
    return html;
  }

  // ═══════════════════════════════════════════════════════════
  // Render: Keyboard Shortcuts Modal
  // ═══════════════════════════════════════════════════════════
  var isMac = /Mac|iPod|iPhone|iPad/.test(navigator.platform);
  var MOD = isMac ? "⌘" : "Ctrl";

  var SHORTCUTS = [
    {
      group: "Widget",
      items: [
        { keys: [MOD, "K"],        label: "Toggle chatbot (open/close)" },
        { keys: [MOD, "/"],        label: "Show this shortcuts panel" },
        { keys: ["Esc"],           label: "Exit fullscreen / close modal" },
      ],
    },
    {
      group: "Chat",
      items: [
        { keys: ["Enter"],         label: "Send message" },
        { keys: ["Shift", "Enter"], label: "New line in message" },
        { keys: [MOD, "N"],        label: "New chat session" },
        { keys: [MOD, "L"],        label: "Clear current chat" },
      ],
    },
    {
      group: "Navigation",
      items: [
        { keys: [MOD, "H"],        label: "Toggle History tab" },
        { keys: [MOD, "J"],        label: "Focus Chat tab" },
        { keys: [MOD, "↑"],        label: "Previous session in history" },
        { keys: [MOD, "↓"],        label: "Next session in history" },
      ],
    },
    {
      group: "Window",
      items: [
        { keys: [MOD, "Shift", "F"], label: "Toggle fullscreen" },
        { keys: [MOD, "Shift", "M"], label: "Toggle maximize" },
        { keys: [MOD, "Shift", "N"], label: "Minimize to bubble" },
      ],
    },
  ];

  function renderShortcutsModal() {
    var html = '<div class="ob-shortcuts-overlay" id="ob-shortcuts-overlay">';
    html += '<div class="ob-shortcuts-modal" onclick="event.stopPropagation()">';
    html += '<div class="ob-shortcuts-hdr">';
    html += '<h3>⌨️ Keyboard Shortcuts</h3>';
    html += '<button class="ob-shortcuts-close" id="ob-shortcuts-close" title="Close (Esc)">✕</button>';
    html += '</div>';
    html += '<div class="ob-shortcuts-body">';
    for (var gi = 0; gi < SHORTCUTS.length; gi++) {
      var g = SHORTCUTS[gi];
      html += '<div class="ob-shortcuts-group">';
      html += '<h4>' + g.group + '</h4>';
      for (var ii = 0; ii < g.items.length; ii++) {
        var s = g.items[ii];
        html += '<div class="ob-shortcut">';
        html += '<span class="ob-shortcut-label">' + esc(s.label) + '</span>';
        html += '<span class="ob-shortcut-keys">';
        for (var ki = 0; ki < s.keys.length; ki++) {
          html += '<kbd class="ob-shortcut-kbd">' + esc(s.keys[ki]) + '</kbd>';
        }
        html += '</span></div>';
      }
      html += '</div>';
    }
    html += '</div></div></div>';
    return html;
  }

  // ═══════════════════════════════════════════════════════════
  // Render: Full panel
  // ═══════════════════════════════════════════════════════════
  function renderPanel() {
    applyPos();

    var modeClass = state.mode === "maximized" ? "ob-maximized" :
                    state.mode === "fullscreen" ? "ob-fullscreen" : "";

    var roleClass = grafanaUser.role.toLowerCase().includes("admin") ? "ob-role-admin" :
                    grafanaUser.role.toLowerCase() === "editor" ? "ob-role-editor" :
                    "ob-role-viewer";

    var chatCount = state.sessions.filter(function(s) { return s.msgs.length > 0; }).length;

    var body = state.view === "history" ? renderHistoryTab() : renderChatTab();

    var showInput = state.view === "chat";
    var inputArea = showInput ? (
      '<div class="ob-in-area"><div class="ob-in-row">' +
        '<textarea class="ob-in" id="ob-input" rows="1" placeholder="Ask about observability..."></textarea>' +
        (state.streaming
          ? '<button class="ob-stop" id="ob-stop">' + ICO_STOP + '</button>'
          : '<button class="ob-send" id="ob-send">' + ICO_SEND + '</button>') +
      '</div></div>'
    ) : '';

    root.innerHTML =
      '<div class="ob-panel ' + modeClass + '">' +
        // Header
        '<div class="ob-hdr" id="ob-hdr">' +
          '<div class="ob-hdr-icon">' + ICO_BOT + '</div>' +
          '<div style="flex:1"><div class="ob-title">O11yBot</div><div class="ob-sub">' + (grafanaUser.role) + ' · drag to move</div></div>' +
          '<div class="ob-acts">' +
            '<button class="ob-hbtn" id="ob-min" title="Minimize">' + ICO_MIN + '</button>' +
            '<button class="ob-hbtn" id="ob-max" title="' + (state.mode === "maximized" ? "Restore" : "Maximize") + '">' + ICO_MAX + '</button>' +
            '<button class="ob-hbtn" id="ob-full" title="' + (state.mode === "fullscreen" ? "Exit fullscreen" : "Fullscreen") + '">' + ICO_FULL + '</button>' +
            '<button class="ob-hbtn" id="ob-close" title="Close">' + ICO_CLOSE + '</button>' +
          '</div>' +
        '</div>' +
        // Tabs
        '<div class="ob-tabs">' +
          '<div class="ob-tab ' + (state.view === "chat" ? "active" : "") + '" data-tab="chat">💬 Chat</div>' +
          '<div class="ob-tab ' + (state.view === "history" ? "active" : "") + '" data-tab="history">🕑 History <span class="ob-tab-badge">' + chatCount + '</span></div>' +
        '</div>' +
        // Body
        body +
        // Footer
        '<div class="ob-footer">' +
          '<div class="ob-user-badge"><span>●</span> ' + esc(grafanaUser.name) + '</div>' +
          '<div class="ob-role-badge ' + roleClass + '">' + grafanaUser.role + '</div>' +
          '<button class="ob-kbd-btn" id="ob-kbd" title="Keyboard shortcuts (⌘/)"><svg viewBox="0 0 24 24"><path d="M20 5H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V7a2 2 0 00-2-2zM6 15H4v-2h2v2zm0-3H4v-2h2v2zm0-3H4V7h2v2zm3 6H7v-2h2v2zm0-3H7v-2h2v2zm0-3H7V7h2v2zm3 6h-2v-2h2v2zm0-3h-2v-2h2v2zm0-3h-2V7h2v2zm3 6h-2v-2h2v2zm0-3h-2v-2h2v2zm0-3h-2V7h2v2zm5 6h-4v-2h4v2zm0-3h-2v-2h2v2zm0-3h-2V7h2v2z"/></svg> Shortcuts</button>' +
          (state.view === "chat" && getActiveSession() ? '<span style="margin-left:auto">' + getActiveSession().msgs.length + ' msgs</span>' : '') +
        '</div>' +
        // Input (only in chat view)
        inputArea +
        // Shortcuts overlay (shown when state.showShortcuts is true)
        (state.showShortcuts ? renderShortcutsModal() : '') +
      '</div>';

    wireEvents();
    scrollToBottom();
  }

  function wireEvents() {
    // Header drag — use addEventListener to not get overridden
    var hdr = document.getElementById("ob-hdr");
    if (hdr) {
      hdr.addEventListener("mousedown", startDrag);
    }

    // Shortcuts button + overlay
    var kbdBtn = document.getElementById("ob-kbd");
    if (kbdBtn) kbdBtn.onclick = function(ev) {
      ev.stopPropagation();
      state.showShortcuts = true;
      renderPanel();
    };
    var kbdClose = document.getElementById("ob-shortcuts-close");
    if (kbdClose) kbdClose.onclick = function() {
      state.showShortcuts = false;
      renderPanel();
    };
    var kbdOverlay = document.getElementById("ob-shortcuts-overlay");
    if (kbdOverlay) kbdOverlay.onclick = function() {
      state.showShortcuts = false;
      renderPanel();
    };

    // Window controls
    var closeBtn = document.getElementById("ob-close");
    if (closeBtn) closeBtn.onclick = function() {
      state.open = false; state.mode = "normal"; saveState(); renderFab();
    };
    var minBtn = document.getElementById("ob-min");
    if (minBtn) minBtn.onclick = function() {
      state.open = false; saveState(); renderFab();
    };
    var maxBtn = document.getElementById("ob-max");
    if (maxBtn) maxBtn.onclick = function() {
      state.mode = state.mode === "maximized" ? "normal" : "maximized";
      saveState(); renderPanel();
    };
    var fullBtn = document.getElementById("ob-full");
    if (fullBtn) fullBtn.onclick = function() {
      state.mode = state.mode === "fullscreen" ? "normal" : "fullscreen";
      saveState(); renderPanel();
    };

    // Tabs
    var tabs = root.querySelectorAll(".ob-tab");
    for (var ti = 0; ti < tabs.length; ti++) {
      tabs[ti].onclick = function() {
        state.view = this.dataset.tab;
        saveState();
        renderPanel();
      };
    }

    if (state.view === "chat") {
      var inp = document.getElementById("ob-input");
      if (inp) {
        inp.onkeydown = function(ev) {
          if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(inp.value); }
        };
        inp.focus();
      }
      var sendBtn = document.getElementById("ob-send");
      if (sendBtn) sendBtn.onclick = function() { send(document.getElementById("ob-input").value); };
      var stopBtn = document.getElementById("ob-stop");
      if (stopBtn) stopBtn.onclick = function() {
        if (abortCtrl) abortCtrl.abort();
        state.streaming = false;
        renderPanel();
      };
      // Welcome suggestions (legacy + new quick-actions)
      var suggs = root.querySelectorAll(".ob-sugg");
      for (var sb = 0; sb < suggs.length; sb++) {
        suggs[sb].onclick = function() { send(this.textContent); };
      }
      // Quick-action buttons
      var qas = root.querySelectorAll(".ob-qa-btn");
      for (var qi = 0; qi < qas.length; qi++) {
        qas[qi].onclick = function() {
          var q = this.getAttribute("data-q");
          // If query ends with space (e.g., "search dashboards "), focus input with prefix
          if (q.endsWith(" ")) {
            var inp = document.getElementById("ob-input");
            if (inp) { inp.value = q; inp.focus(); }
          } else {
            send(q);
          }
        };
      }
    }

    if (state.view === "history") {
      // New chat (both the toolbar button and empty-state button)
      var newBtn = document.getElementById("ob-new-chat");
      var emptyBtn = document.getElementById("ob-new-chat-empty");
      var startNew = function() {
        newSession();
        state.view = "chat";
        state.historySearch = "";
        saveState();
        renderPanel();
      };
      if (newBtn) newBtn.onclick = startNew;
      if (emptyBtn) emptyBtn.onclick = startNew;

      // Search input — live filtering
      var searchInp = document.getElementById("ob-history-search");
      if (searchInp) {
        searchInp.oninput = function() {
          // Save cursor position before re-render
          var pos = this.selectionStart;
          state.historySearch = this.value;
          // Only re-render the list, keep the input focused
          var listEl = root.querySelector(".ob-history-list");
          if (listEl && listEl.parentElement) {
            // Build just the new list HTML and replace
            var tempHtml = renderHistoryTab();
            var tmp = document.createElement("div");
            tmp.innerHTML = tempHtml;
            var newWrap = tmp.querySelector(".ob-history-wrap");
            if (newWrap) {
              var oldWrap = root.querySelector(".ob-history-wrap");
              if (oldWrap) oldWrap.parentElement.replaceChild(newWrap, oldWrap);
            }
            // Re-wire events (for the new DOM) AND re-focus the search input
            wireEvents();
            var newInp = document.getElementById("ob-history-search");
            if (newInp) {
              newInp.focus();
              newInp.setSelectionRange(pos, pos);
            }
          }
        };
      }

      // Select session
      var items = root.querySelectorAll(".ob-history-item");
      for (var hi = 0; hi < items.length; hi++) {
        items[hi].onclick = function(ev) {
          // Ignore clicks on action buttons
          if (ev.target.closest(".ob-hi-actions")) return;
          selectSession(this.dataset.sid);
          renderPanel();
        };
      }

      // Delete session
      var dels = root.querySelectorAll(".ob-hi-del");
      for (var di = 0; di < dels.length; di++) {
        dels[di].onclick = function(ev) {
          ev.stopPropagation();
          if (confirm("Delete this chat?")) {
            deleteSession(this.dataset.del);
            renderPanel();
          }
        };
      }

      // Star / unstar session
      var stars = root.querySelectorAll(".ob-hi-star");
      for (var sti = 0; sti < stars.length; sti++) {
        stars[sti].onclick = function(ev) {
          ev.stopPropagation();
          var id = this.dataset.star;
          state.starredIds = state.starredIds || [];
          var idx = state.starredIds.indexOf(id);
          if (idx >= 0) state.starredIds.splice(idx, 1);
          else state.starredIds.push(id);
          saveState();
          renderPanel();
        };
      }
    }
  }

  function scrollToBottom() {
    var msgsEl = document.getElementById("ob-msgs");
    if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  function startDrag(ev) {
    // Don't drag if clicking on a button or interactive element
    if (ev.target.tagName === "BUTTON" || ev.target.closest("button")) return;
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA" || ev.target.tagName === "SELECT") return;
    // Can't drag while maximized/fullscreen
    if (state.mode === "maximized" || state.mode === "fullscreen") return;

    ev.preventDefault();
    ev.stopPropagation();

    var rect = root.getBoundingClientRect();
    drag = {
      active: true,
      ox: ev.clientX - rect.left,
      oy: ev.clientY - rect.top,
    };
    document.body.style.userSelect = "none";

    var onMove = function(ev2) {
      if (!drag.active) return;
      ev2.preventDefault();
      var nx = Math.max(0, Math.min(window.innerWidth - 60, ev2.clientX - drag.ox));
      var ny = Math.max(0, Math.min(window.innerHeight - 60, ev2.clientY - drag.oy));
      state.posX = nx;
      state.posY = ny;
      root.style.left = nx + "px";
      root.style.top = ny + "px";
      root.style.right = "auto";
      root.style.bottom = "auto";
    };
    var onUp = function() {
      drag.active = false;
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      saveState();
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  // ═══════════════════════════════════════════════════════════
  // Append to current chat (streaming)
  // ═══════════════════════════════════════════════════════════
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

  function appendBotMessage(botMsg) {
    var msgsEl = document.getElementById("ob-msgs");
    if (!msgsEl) return;
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
    scrollToBottom();
  }

  // ═══════════════════════════════════════════════════════════
  // Send (writes to active session)
  // ═══════════════════════════════════════════════════════════
  function send(text) {
    if (!text || !text.trim() || state.streaming) return;
    text = text.trim();

    // Ensure we have an active session
    var session = getActiveSession();
    if (!session) {
      session = newSession();
    }

    var now = Date.now();
    var userMsg = { role: "user", content: text, id: "u" + now, ts: now };
    var botMsg = { role: "bot", content: "", id: "b" + now, ts: now, streaming: true, cost: 0, tokens: 0 };

    session.msgs.push(userMsg);
    session.msgs.push(botMsg);
    session.updatedAt = now;
    // Auto-title from first user message
    if (session.msgs.filter(function(m) { return m.role === "user"; }).length === 1) {
      session.title = autoTitle(session);
    }
    state.streaming = true;
    saveState();

    // Clear input + append directly (no full re-render)
    var inp = document.getElementById("ob-input");
    if (inp) inp.value = "";
    appendUserMessage(userMsg);
    appendBotMessage(botMsg);

    // Build messages array
    var allMsgs = [];
    for (var i = 0; i < session.msgs.length - 1; i++) {
      var m = session.msgs[i];
      allMsgs.push({ role: m.role === "user" ? "user" : "assistant", content: m.content });
    }

    abortCtrl = new AbortController();

    console.log("[O11yBot] POST", ORCHESTRATOR + "/api/v1/chat", "role:", grafanaUser.role);

    fetch(ORCHESTRATOR + "/api/v1/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Grafana-User": grafanaUser.login,
        "X-Grafana-Org-Id": String(grafanaUser.orgId),
        "X-Grafana-Role": grafanaUser.role,
      },
      body: JSON.stringify({
        messages: allMsgs,
        system: "You are O11yBot, an assistant embedded in Grafana for " + grafanaUser.name +
                " (role: " + grafanaUser.role + "). Help with observability. Be brief.",
        max_tokens: 4096, temperature: 0.2, stream: true,
      }),
      signal: abortCtrl.signal,
    }).then(function(resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      if (!resp.body) throw new Error("No response body");
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      var acc = "";

      function read() {
        return reader.read().then(function(r) {
          if (r.done) { finish(); return; }
          buf += decoder.decode(r.value, { stream: true });
          buf = buf.replace(/\r\n/g, "\n");
          var sep;
          while ((sep = buf.indexOf("\n\n")) !== -1) {
            var frame = buf.slice(0, sep);
            buf = buf.slice(sep + 2);
            for (var li = 0; li < frame.split("\n").length; li++) {
              var line = frame.split("\n")[li];
              if (line.indexOf("data: ") !== 0) continue;
              var js = line.slice(6);
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
                } else if (ev.type === "error") {
                  acc += "\n\n**Error:** " + ev.message;
                  botMsg.content = acc;
                  if (currentBotBubble) currentBotBubble.innerHTML = fmtMd(acc);
                }
              } catch(e) {}
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
        if (currentBotBubble) currentBotBubble.innerHTML = '<div style="color:#ef4444">' + esc(err.message) + '</div>';
      }
      finish();
    });

    function finish() {
      botMsg.streaming = false;
      state.streaming = false;
      session.updatedAt = Date.now();
      if (currentTypingEl) currentTypingEl.remove();
      currentTypingEl = null;
      saveState();
      // Update footer (msg count)
      var footer = root.querySelector(".ob-footer");
      if (footer) {
        var countEl = footer.querySelector("span:last-child");
        if (countEl && countEl.textContent.indexOf("msgs") >= 0) {
          countEl.textContent = session.msgs.length + " msgs";
        }
      }
    }
  }

  // ═══════════════════════════════════════════════════════════
  // Global Keyboard Shortcuts
  // ═══════════════════════════════════════════════════════════
  function selectNextSession(direction) {
    // direction: -1 (previous/up), +1 (next/down)
    if (state.sessions.length === 0) return;
    var sorted = state.sessions.slice().sort(function(a, b) { return b.updatedAt - a.updatedAt; });
    var idx = sorted.findIndex(function(s) { return s.id === state.activeSessionId; });
    if (idx < 0) idx = 0;
    else idx = (idx + direction + sorted.length) % sorted.length;
    selectSession(sorted[idx].id);
    state.view = "history";
    renderPanel();
  }

  document.addEventListener("keydown", function(ev) {
    var mod = ev.metaKey || ev.ctrlKey;

    // ─── Close shortcuts modal with Esc ───
    if (ev.key === "Escape" && state.showShortcuts) {
      ev.preventDefault();
      state.showShortcuts = false;
      renderPanel();
      return;
    }

    // ─── Esc to exit fullscreen/maximized ───
    if (ev.key === "Escape" && state.open && (state.mode === "fullscreen" || state.mode === "maximized")) {
      ev.preventDefault();
      state.mode = "normal"; saveState(); renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + K: toggle widget open/close ───
    if (mod && !ev.shiftKey && ev.key.toLowerCase() === "k") {
      ev.preventDefault();
      if (state.open) {
        state.open = false; saveState(); renderFab();
      } else {
        state.open = true; renderPanel();
      }
      return;
    }

    // ─── Cmd/Ctrl + /: show shortcuts help ───
    if (mod && ev.key === "/") {
      ev.preventDefault();
      if (!state.open) { state.open = true; renderPanel(); }
      state.showShortcuts = !state.showShortcuts;
      renderPanel();
      return;
    }

    // Remaining shortcuts require widget to be open
    if (!state.open) return;

    // ─── Cmd/Ctrl + N: new chat ───
    if (mod && !ev.shiftKey && ev.key.toLowerCase() === "n") {
      ev.preventDefault();
      newSession();
      state.view = "chat";
      saveState();
      renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + L: clear current chat ───
    if (mod && !ev.shiftKey && ev.key.toLowerCase() === "l") {
      ev.preventDefault();
      var s = getActiveSession();
      if (s) {
        s.msgs = [];
        s.title = "New chat";
        s.updatedAt = Date.now();
        saveState();
        renderPanel();
      }
      return;
    }

    // ─── Cmd/Ctrl + H: toggle history tab ───
    if (mod && !ev.shiftKey && ev.key.toLowerCase() === "h") {
      ev.preventDefault();
      state.view = state.view === "history" ? "chat" : "history";
      saveState();
      renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + J: focus chat tab ───
    if (mod && !ev.shiftKey && ev.key.toLowerCase() === "j") {
      ev.preventDefault();
      state.view = "chat";
      saveState();
      renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + ArrowUp / ArrowDown: prev/next session ───
    if (mod && ev.key === "ArrowUp") {
      ev.preventDefault();
      selectNextSession(-1);
      return;
    }
    if (mod && ev.key === "ArrowDown") {
      ev.preventDefault();
      selectNextSession(1);
      return;
    }

    // ─── Cmd/Ctrl + Shift + F: fullscreen ───
    if (mod && ev.shiftKey && ev.key.toLowerCase() === "f") {
      ev.preventDefault();
      state.mode = state.mode === "fullscreen" ? "normal" : "fullscreen";
      saveState(); renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + Shift + M: maximize ───
    if (mod && ev.shiftKey && ev.key.toLowerCase() === "m") {
      ev.preventDefault();
      state.mode = state.mode === "maximized" ? "normal" : "maximized";
      saveState(); renderPanel();
      return;
    }

    // ─── Cmd/Ctrl + Shift + N: minimize to bubble ───
    if (mod && ev.shiftKey && ev.key.toLowerCase() === "n") {
      ev.preventDefault();
      state.open = false;
      saveState();
      renderFab();
      return;
    }
  });

  // ═══════════════════════════════════════════════════════════
  // Init
  // ═══════════════════════════════════════════════════════════
  if (state.open) renderPanel(); else renderFab();
  console.log("%c[O11yBot] v" + WIDGET_VERSION + " ready · User: " + grafanaUser.login + " · Role: " + grafanaUser.role + " · Sessions: " + state.sessions.length,
    "color:#22c55e;font-weight:bold;");
})();
