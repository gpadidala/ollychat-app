/**
 * O11yBot — Floating Grafana Chatbot Widget
 *
 * Injects a draggable, resizable chat bubble on EVERY Grafana page.
 * Works like Grafana Assistant / Intercom — always available,
 * movable to any corner, persists across page navigation.
 *
 * Deployable to any Grafana instance as an app plugin.
 */
define(["react", "react-dom", "@grafana/data", "@grafana/ui", "@grafana/runtime"],
function(React, ReactDOM, grafanaData, grafanaUI, grafanaRuntime) {
  "use strict";

  var e = React.createElement;
  var useState = React.useState;
  var useEffect = React.useEffect;
  var useRef = React.useRef;
  var useCallback = React.useCallback;

  // ─────────────────────────────────────────────────────────
  // Configuration
  // ─────────────────────────────────────────────────────────
  var ORCHESTRATOR_URL = "http://localhost:8000";
  var BOT_NAME = "O11yBot";
  var WIDGET_ID = "o11ybot-floating-widget";
  var STORAGE_KEY = "o11ybot-state";

  // ─────────────────────────────────────────────────────────
  // CSS Styles (injected into document head)
  // ─────────────────────────────────────────────────────────
  var CSS = '\
  #' + WIDGET_ID + ' {\
    position: fixed;\
    z-index: 999999;\
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;\
    font-size: 14px;\
    color: #e0e0e0;\
  }\
  .o11ybot-fab {\
    width: 56px; height: 56px;\
    border-radius: 50%;\
    background: linear-gradient(135deg, #ff6600 0%, #f59e0b 100%);\
    border: none;\
    cursor: pointer;\
    display: flex; align-items: center; justify-content: center;\
    box-shadow: 0 4px 20px rgba(255,102,0,0.4), 0 2px 8px rgba(0,0,0,0.3);\
    transition: transform 0.2s, box-shadow 0.2s;\
    position: relative;\
  }\
  .o11ybot-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(255,102,0,0.5); }\
  .o11ybot-fab svg { width: 28px; height: 28px; fill: white; }\
  .o11ybot-fab .o11ybot-badge {\
    position: absolute; top: -2px; right: -2px;\
    width: 14px; height: 14px; border-radius: 50%;\
    background: #22c55e; border: 2px solid #111217;\
  }\
  .o11ybot-panel {\
    width: 420px; height: 560px;\
    background: #111217;\
    border: 1px solid #2a2a3e;\
    border-radius: 12px;\
    display: flex; flex-direction: column;\
    box-shadow: 0 12px 48px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3);\
    overflow: hidden;\
    resize: both;\
    min-width: 340px; min-height: 400px;\
    max-width: 90vw; max-height: 85vh;\
  }\
  .o11ybot-header {\
    display: flex; align-items: center; gap: 10px;\
    padding: 12px 16px;\
    background: linear-gradient(135deg, #1a1025 0%, #111217 100%);\
    border-bottom: 1px solid #2a2a3e;\
    cursor: grab; user-select: none;\
  }\
  .o11ybot-header:active { cursor: grabbing; }\
  .o11ybot-header-icon {\
    width: 32px; height: 32px; border-radius: 50%;\
    background: linear-gradient(135deg, #ff6600, #f59e0b);\
    display: flex; align-items: center; justify-content: center;\
    flex-shrink: 0;\
  }\
  .o11ybot-header-icon svg { width: 18px; height: 18px; fill: white; }\
  .o11ybot-header-title { font-weight: 600; font-size: 15px; flex: 1; }\
  .o11ybot-header-sub { font-size: 11px; color: #888; margin-top: 1px; }\
  .o11ybot-header-actions { display: flex; gap: 4px; }\
  .o11ybot-header-btn {\
    width: 28px; height: 28px; border-radius: 6px;\
    background: transparent; border: 1px solid transparent;\
    color: #888; cursor: pointer; display: flex;\
    align-items: center; justify-content: center;\
    transition: all 0.15s;\
  }\
  .o11ybot-header-btn:hover { background: #ffffff10; border-color: #ffffff15; color: #ccc; }\
  .o11ybot-header-btn svg { width: 16px; height: 16px; fill: currentColor; }\
  .o11ybot-messages {\
    flex: 1; overflow-y: auto; padding: 16px;\
    scroll-behavior: smooth;\
  }\
  .o11ybot-messages::-webkit-scrollbar { width: 5px; }\
  .o11ybot-messages::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }\
  .o11ybot-msg { margin-bottom: 14px; display: flex; gap: 8px; }\
  .o11ybot-msg-user { flex-direction: row-reverse; }\
  .o11ybot-msg-avatar {\
    width: 28px; height: 28px; border-radius: 50%;\
    display: flex; align-items: center; justify-content: center;\
    flex-shrink: 0; font-size: 12px; font-weight: 600;\
  }\
  .o11ybot-msg-user .o11ybot-msg-avatar { background: #2563eb33; color: #60a5fa; }\
  .o11ybot-msg-bot .o11ybot-msg-avatar { background: #ff660033; color: #f59e0b; }\
  .o11ybot-msg-bubble {\
    max-width: 82%; padding: 10px 14px;\
    border-radius: 12px; line-height: 1.55;\
    word-break: break-word; white-space: pre-wrap;\
    font-size: 13.5px;\
  }\
  .o11ybot-msg-user .o11ybot-msg-bubble {\
    background: #1e3a5f; border: 1px solid #2563eb44;\
    border-bottom-right-radius: 4px;\
  }\
  .o11ybot-msg-bot .o11ybot-msg-bubble {\
    background: #1a1a2e; border: 1px solid #2a2a3e;\
    border-bottom-left-radius: 4px;\
  }\
  .o11ybot-msg-bubble code {\
    background: #0d0d12; padding: 2px 5px; border-radius: 4px;\
    font-family: "JetBrains Mono", "Fira Code", monospace; font-size: 12px;\
  }\
  .o11ybot-msg-bubble pre {\
    background: #0d0d12; padding: 10px; border-radius: 6px;\
    overflow-x: auto; margin: 8px 0; font-size: 12px;\
    font-family: "JetBrains Mono", monospace;\
    border: 1px solid #1e1e2e;\
  }\
  .o11ybot-msg-meta {\
    font-size: 11px; color: #555; margin-top: 4px;\
    display: flex; gap: 8px;\
  }\
  .o11ybot-cost { color: #f59e0b; font-family: monospace; }\
  .o11ybot-typing { display: flex; gap: 4px; padding: 4px 0; }\
  .o11ybot-typing span {\
    width: 6px; height: 6px; background: #f59e0b; border-radius: 50%;\
    animation: o11ybot-bounce 1.4s infinite;\
  }\
  .o11ybot-typing span:nth-child(2) { animation-delay: 0.2s; }\
  .o11ybot-typing span:nth-child(3) { animation-delay: 0.4s; }\
  @keyframes o11ybot-bounce {\
    0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }\
    40% { transform: translateY(-8px); opacity: 1; }\
  }\
  .o11ybot-input-area {\
    padding: 12px; border-top: 1px solid #2a2a3e;\
    background: #0d0d12;\
  }\
  .o11ybot-input-row { display: flex; gap: 8px; align-items: flex-end; }\
  .o11ybot-input {\
    flex: 1; background: #181b23; border: 1px solid #2a2a3e;\
    border-radius: 8px; color: #e0e0e0; padding: 10px 14px;\
    font-size: 13.5px; resize: none; outline: none;\
    font-family: inherit; min-height: 20px; max-height: 120px;\
    transition: border-color 0.2s;\
  }\
  .o11ybot-input:focus { border-color: #ff660066; }\
  .o11ybot-input::placeholder { color: #555; }\
  .o11ybot-send-btn {\
    width: 38px; height: 38px; border-radius: 8px;\
    background: linear-gradient(135deg, #ff6600, #f59e0b);\
    border: none; cursor: pointer; display: flex;\
    align-items: center; justify-content: center;\
    transition: opacity 0.2s; flex-shrink: 0;\
  }\
  .o11ybot-send-btn:disabled { opacity: 0.3; cursor: default; }\
  .o11ybot-send-btn:not(:disabled):hover { opacity: 0.85; }\
  .o11ybot-send-btn svg { width: 18px; height: 18px; fill: white; }\
  .o11ybot-stop-btn {\
    width: 38px; height: 38px; border-radius: 8px;\
    background: #dc2626; border: none; cursor: pointer;\
    display: flex; align-items: center; justify-content: center;\
    flex-shrink: 0;\
  }\
  .o11ybot-stop-btn svg { width: 16px; height: 16px; fill: white; }\
  .o11ybot-model-bar {\
    display: flex; align-items: center; gap: 6px;\
    padding: 6px 12px; font-size: 11px; color: #666;\
    border-top: 1px solid #1a1a2e;\
  }\
  .o11ybot-model-select {\
    background: #111217; border: 1px solid #2a2a3e; border-radius: 4px;\
    color: #888; padding: 2px 6px; font-size: 11px; outline: none;\
  }\
  .o11ybot-welcome {\
    display: flex; flex-direction: column; align-items: center;\
    justify-content: center; height: 100%; text-align: center;\
    padding: 20px; color: #888;\
  }\
  .o11ybot-welcome h3 { color: #e0e0e0; margin: 0 0 6px; font-size: 17px; }\
  .o11ybot-welcome p { font-size: 13px; max-width: 280px; margin: 0 0 16px; line-height: 1.5; }\
  .o11ybot-suggestions { display: flex; flex-direction: column; gap: 6px; width: 100%; }\
  .o11ybot-suggestion {\
    padding: 9px 14px; background: #181b23;\
    border: 1px solid #2a2a3e; border-radius: 8px;\
    cursor: pointer; text-align: left; color: #ccc;\
    font-size: 12.5px; transition: all 0.15s;\
  }\
  .o11ybot-suggestion:hover { background: #1e1e2e; border-color: #ff660044; color: #f59e0b; }\
  .o11ybot-tool {\
    margin: 6px 0; padding: 8px 10px;\
    background: #0d0d12; border: 1px solid #2a2a3e;\
    border-radius: 6px; font-size: 12px;\
    font-family: "JetBrains Mono", monospace;\
  }\
  .o11ybot-tool-name { color: #f59e0b; font-weight: 600; }\
  .o11ybot-tool-result { color: #22c55e; }\
  .o11ybot-tool-error { color: #ef4444; }\
  ';

  // ─────────────────────────────────────────────────────────
  // SVG Icons
  // ─────────────────────────────────────────────────────────
  var ICON_BOT = '<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 012 2v1h4a3 3 0 013 3v8a3 3 0 01-3 3H6a3 3 0 01-3-3V8a3 3 0 013-3h4V4a2 2 0 012-2zm-3 9a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM8 17h8v1a1 1 0 01-1 1H9a1 1 0 01-1-1v-1z"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var ICON_MIN = '<svg viewBox="0 0 24 24"><path d="M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>';
  var ICON_CLEAR = '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M5 6v14a2 2 0 002 2h10a2 2 0 002-2V6" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="white" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var ICON_STOP = '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>';

  // ─────────────────────────────────────────────────────────
  // Persistence helpers
  // ─────────────────────────────────────────────────────────
  function loadState() {
    try {
      var s = localStorage.getItem(STORAGE_KEY);
      return s ? JSON.parse(s) : null;
    } catch(e) { return null; }
  }
  function saveState(state) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch(e) {}
  }

  // ─────────────────────────────────────────────────────────
  // The Floating Chat Widget
  // ─────────────────────────────────────────────────────────
  function O11yBotWidget() {
    var saved = loadState() || {};
    var _s1 = useState(saved.open || false); var open = _s1[0]; var setOpen = _s1[1];
    var _s2 = useState(saved.messages || []); var messages = _s2[0]; var setMessages = _s2[1];
    var _s3 = useState(""); var input = _s3[0]; var setInput = _s3[1];
    var _s4 = useState(false); var streaming = _s4[0]; var setStreaming = _s4[1];
    var _s5 = useState(null); var error = _s5[0]; var setError = _s5[1];
    var _s6 = useState(saved.model || "claude-sonnet-4-6"); var model = _s6[0]; var setModel = _s6[1];
    var _s7 = useState(saved.pos || { x: null, y: null }); var pos = _s7[0]; var setPos = _s7[1];
    var _s8 = useState(saved.corner || "bottom-right"); var corner = _s8[0]; var setCorner = _s8[1];

    var messagesEndRef = useRef(null);
    var panelRef = useRef(null);
    var dragRef = useRef({ dragging: false, startX: 0, startY: 0, offsetX: 0, offsetY: 0 });
    var abortRef = useRef(null);
    var msgIdRef = useRef(0);

    // Auto-scroll
    useEffect(function() {
      if (messagesEndRef.current) messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Persist state
    useEffect(function() {
      saveState({ open: open, messages: messages.slice(-50), model: model, pos: pos, corner: corner });
    }, [open, messages, model, pos, corner]);

    // Corner positioning
    function getCornerStyle() {
      if (pos.x !== null && pos.y !== null) {
        return { left: pos.x + "px", top: pos.y + "px" };
      }
      var s = {};
      if (corner.indexOf("bottom") >= 0) s.bottom = "24px"; else s.top = "80px";
      if (corner.indexOf("right") >= 0) s.right = "24px"; else s.left = "24px";
      return s;
    }

    // Drag handlers
    function onDragStart(ev) {
      if (ev.target.tagName === "SELECT" || ev.target.tagName === "BUTTON") return;
      var rect = panelRef.current ? panelRef.current.parentElement.getBoundingClientRect() : { left: 0, top: 0 };
      dragRef.current = {
        dragging: true,
        startX: ev.clientX,
        startY: ev.clientY,
        offsetX: ev.clientX - rect.left,
        offsetY: ev.clientY - rect.top,
      };
      document.addEventListener("mousemove", onDragMove);
      document.addEventListener("mouseup", onDragEnd);
    }
    function onDragMove(ev) {
      if (!dragRef.current.dragging) return;
      var newX = ev.clientX - dragRef.current.offsetX;
      var newY = ev.clientY - dragRef.current.offsetY;
      newX = Math.max(0, Math.min(window.innerWidth - 100, newX));
      newY = Math.max(0, Math.min(window.innerHeight - 100, newY));
      setPos({ x: newX, y: newY });
    }
    function onDragEnd() {
      dragRef.current.dragging = false;
      document.removeEventListener("mousemove", onDragMove);
      document.removeEventListener("mouseup", onDragEnd);
    }

    // Send message
    function sendMessage(text) {
      if (!text || !text.trim() || streaming) return;
      text = text.trim();
      var uid = ++msgIdRef.current;
      var userMsg = { id: "u" + uid, role: "user", content: text, ts: Date.now() };
      var botMsg = { id: "b" + uid, role: "bot", content: "", ts: Date.now(), streaming: true };

      setMessages(function(prev) { return prev.concat([userMsg, botMsg]); });
      setInput("");
      setStreaming(true);
      setError(null);

      var allMsgs = messages.concat([userMsg]).map(function(m) {
        return { role: m.role === "user" ? "user" : "assistant", content: m.content };
      });

      var controller = new AbortController();
      abortRef.current = controller;

      fetch(ORCHESTRATOR_URL + "/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: model,
          messages: allMsgs,
          system: "You are O11yBot, a concise AI assistant embedded in Grafana. You help with observability, infrastructure monitoring, incident response, and SRE tasks. You have access to MCP tools for querying dashboards, datasources, alerts, metrics (PromQL), logs (LogQL), and traces (TraceQL). Be brief and actionable. Use code blocks for queries.",
          max_tokens: 4096,
          temperature: 0.2,
          stream: true
        }),
        signal: controller.signal
      }).then(function(resp) {
        if (!resp.ok) throw new Error("API error: " + resp.status);
        var reader = resp.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";
        var accumulated = "";
        var cost = 0;
        var tokens = 0;

        function read() {
          return reader.read().then(function(result) {
            if (result.done) {
              setStreaming(false);
              setMessages(function(prev) {
                return prev.map(function(m) {
                  return m.id === botMsg.id ? Object.assign({}, m, { streaming: false, cost: cost, tokens: tokens }) : m;
                });
              });
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var sep;
            while ((sep = buffer.indexOf("\n\n")) !== -1) {
              var frame = buffer.slice(0, sep);
              buffer = buffer.slice(sep + 2);
              var lines = frame.split("\n");
              for (var i = 0; i < lines.length; i++) {
                if (lines[i].indexOf("data: ") !== 0) continue;
                var jsonStr = lines[i].slice(6);
                if (jsonStr === "[DONE]") continue;
                try {
                  var evt = JSON.parse(jsonStr);
                  if (evt.type === "text") {
                    accumulated += evt.delta;
                    setMessages(function(prev) {
                      return prev.map(function(m) {
                        return m.id === botMsg.id ? Object.assign({}, m, { content: accumulated }) : m;
                      });
                    });
                  } else if (evt.type === "usage") {
                    cost = evt.costUsd || 0;
                    tokens = (evt.usage || {}).totalTokens || 0;
                  } else if (evt.type === "tool_start") {
                    accumulated += "\n<div class='o11ybot-tool'><span class='o11ybot-tool-name'>" + evt.name + "</span> " + JSON.stringify(evt.input).slice(0,150) + "</div>";
                  } else if (evt.type === "tool_result") {
                    var preview = evt.error ? "<span class='o11ybot-tool-error'>Error: " + evt.error + "</span>" : "<span class='o11ybot-tool-result'>OK (" + evt.durationMs + "ms)</span>";
                    accumulated += "<div class='o11ybot-tool'>Result: " + preview + "</div>\n";
                  } else if (evt.type === "error") {
                    setError(evt.message);
                  }
                } catch(e) {}
              }
            }
            return read();
          });
        }
        return read();
      }).catch(function(err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          setStreaming(false);
          setMessages(function(prev) {
            return prev.map(function(m) {
              return m.id === botMsg.id ? Object.assign({}, m, { content: "Error: " + err.message, streaming: false }) : m;
            });
          });
        }
      });
    }

    function stopStreaming() {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = null;
      setStreaming(false);
    }

    function clearChat() { setMessages([]); setError(null); }

    var suggestions = [
      "Show top 5 services by error rate",
      "List all Grafana dashboards",
      "Check health of Grafana datasources",
      "Generate PromQL for CPU usage by pod"
    ];

    // ── Render ──
    var posStyle = getCornerStyle();

    // FAB (floating action button) — shown when panel is closed
    if (!open) {
      return e("div", { id: WIDGET_ID, style: posStyle },
        e("button", {
          className: "o11ybot-fab",
          onClick: function() { setOpen(true); },
          title: BOT_NAME + " — Click to chat",
          dangerouslySetInnerHTML: { __html: ICON_BOT }
        }),
        e("div", { className: "o11ybot-badge" })
      );
    }

    // Chat panel — shown when open
    return e("div", { id: WIDGET_ID, style: posStyle },
      e("div", { className: "o11ybot-panel", ref: panelRef },
        // Header (draggable)
        e("div", { className: "o11ybot-header", onMouseDown: onDragStart },
          e("div", { className: "o11ybot-header-icon", dangerouslySetInnerHTML: { __html: ICON_BOT } }),
          e("div", { style: { flex: 1 } },
            e("div", { className: "o11ybot-header-title" }, BOT_NAME),
            e("div", { className: "o11ybot-header-sub" }, "O11y Assistant \u2022 drag to move")
          ),
          e("div", { className: "o11ybot-header-actions" },
            e("button", { className: "o11ybot-header-btn", onClick: clearChat, title: "Clear chat", dangerouslySetInnerHTML: { __html: ICON_CLEAR } }),
            e("button", { className: "o11ybot-header-btn", onClick: function() { setOpen(false); }, title: "Minimize", dangerouslySetInnerHTML: { __html: ICON_MIN } }),
            e("button", { className: "o11ybot-header-btn", onClick: function() { setOpen(false); }, title: "Close", dangerouslySetInnerHTML: { __html: ICON_CLOSE } })
          )
        ),

        // Messages
        e("div", { className: "o11ybot-messages" },
          messages.length === 0 && e("div", { className: "o11ybot-welcome" },
            e("h3", null, "Hey! I'm " + BOT_NAME),
            e("p", null, "Your observability assistant. Ask me about metrics, logs, traces, dashboards, or incidents."),
            e("div", { className: "o11ybot-suggestions" },
              suggestions.map(function(s, i) {
                return e("button", {
                  key: i, className: "o11ybot-suggestion",
                  onClick: function() { sendMessage(s); }
                }, s);
              })
            )
          ),
          messages.map(function(msg) {
            var isUser = msg.role === "user";
            return e("div", { key: msg.id, className: "o11ybot-msg " + (isUser ? "o11ybot-msg-user" : "o11ybot-msg-bot") },
              e("div", { className: "o11ybot-msg-avatar" }, isUser ? "U" : "O"),
              e("div", null,
                e("div", {
                  className: "o11ybot-msg-bubble",
                  dangerouslySetInnerHTML: msg.role === "bot" ? { __html: formatMarkdown(msg.content || "") } : undefined,
                  children: isUser ? msg.content : undefined
                }),
                msg.streaming && e("div", { className: "o11ybot-typing" },
                  e("span"), e("span"), e("span")
                ),
                !isUser && !msg.streaming && (msg.cost > 0 || msg.tokens > 0) && e("div", { className: "o11ybot-msg-meta" },
                  msg.tokens > 0 && e("span", null, msg.tokens + " tok"),
                  msg.cost > 0 && e("span", { className: "o11ybot-cost" }, "$" + msg.cost.toFixed(4))
                )
              )
            );
          }),
          error && e("div", { style: { color: "#ef4444", fontSize: "12px", padding: "8px", background: "#dc262615", borderRadius: 6, margin: "4px 0" } }, error),
          e("div", { ref: messagesEndRef })
        ),

        // Model selector bar
        e("div", { className: "o11ybot-model-bar" },
          e("span", null, "Model:"),
          e("select", {
            className: "o11ybot-model-select",
            value: model,
            onChange: function(ev) { setModel(ev.target.value); }
          },
            e("option", { value: "claude-sonnet-4-6" }, "Sonnet 4.6"),
            e("option", { value: "claude-opus-4-6" }, "Opus 4.6"),
            e("option", { value: "gpt-4o" }, "GPT-4o"),
            e("option", { value: "claude-haiku-4-5" }, "Haiku 4.5"),
            e("option", { value: "gpt-4o-mini" }, "GPT-4o Mini"),
            e("option", { value: "gemini-2.0-flash" }, "Gemini Flash"),
            e("option", { value: "llama3.2:latest" }, "Llama 3.2")
          ),
          e("span", { style: { marginLeft: "auto" } }, messages.length + " msgs")
        ),

        // Input area
        e("div", { className: "o11ybot-input-area" },
          e("div", { className: "o11ybot-input-row" },
            e("textarea", {
              className: "o11ybot-input",
              value: input,
              onChange: function(ev) { setInput(ev.target.value); },
              onKeyDown: function(ev) {
                if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); sendMessage(input); }
              },
              placeholder: streaming ? "Thinking..." : "Ask about observability...",
              rows: 1,
              disabled: streaming
            }),
            streaming
              ? e("button", { className: "o11ybot-stop-btn", onClick: stopStreaming, dangerouslySetInnerHTML: { __html: ICON_STOP } })
              : e("button", { className: "o11ybot-send-btn", onClick: function() { sendMessage(input); }, disabled: !input.trim(), dangerouslySetInnerHTML: { __html: ICON_SEND } })
          )
        )
      )
    );
  }

  // Simple markdown-ish formatting
  function formatMarkdown(text) {
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      // Restore our tool HTML
      .replace(/&lt;div class=&#39;o11ybot-tool/g, "<div class='o11ybot-tool")
      .replace(/&lt;span class=&#39;o11ybot-tool/g, "<span class='o11ybot-tool")
      .replace(/&lt;\/span&gt;/g, "</span>")
      .replace(/&lt;\/div&gt;/g, "</div>")
      // Code blocks
      .replace(/```(\w*)\n([\s\S]*?)```/g, function(_, lang, code) {
        return "<pre><code>" + code.trim() + "</code></pre>";
      })
      // Inline code
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      // Bold
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // Italic
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Line breaks
      .replace(/\n/g, "<br/>");
  }

  // ─────────────────────────────────────────────────────────
  // Inject into Grafana globally
  // ─────────────────────────────────────────────────────────
  function injectWidget() {
    if (document.getElementById(WIDGET_ID)) return;

    // Inject CSS
    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    // Create mount point
    var mount = document.createElement("div");
    mount.id = WIDGET_ID;
    document.body.appendChild(mount);

    // Render React widget
    ReactDOM.render(e(O11yBotWidget), mount);
  }

  // Inject on load and re-inject if DOM changes (SPA navigation)
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(injectWidget, 500);
  } else {
    document.addEventListener("DOMContentLoaded", function() { setTimeout(injectWidget, 500); });
  }

  // Re-inject periodically (handles Grafana SPA navigation)
  setInterval(function() {
    if (!document.getElementById(WIDGET_ID)) {
      injectWidget();
    }
  }, 3000);

  // ─────────────────────────────────────────────────────────
  // Plugin export (Grafana requires this)
  // ─────────────────────────────────────────────────────────
  var plugin = new grafanaData.AppPlugin();
  plugin.setRootPage(function EmptyRoot() {
    // The floating widget is injected globally — no page needed
    return e("div", { style: { padding: 40, textAlign: "center" } },
      e("h2", null, BOT_NAME + " is active!"),
      e("p", null, "The floating chatbot widget is available on every page of Grafana."),
      e("p", null, "Look for the orange chat bubble in the bottom-right corner."),
      e("p", { style: { color: "#888", marginTop: 20 } },
        "Orchestrator: ", e("a", { href: ORCHESTRATOR_URL, target: "_blank" }, ORCHESTRATOR_URL)),
      e("p", { style: { color: "#888" } },
        "Bifrost MCP: ", e("a", { href: "http://localhost:8765", target: "_blank" }, "http://localhost:8765"))
    );
  });

  return { plugin: plugin };
});
