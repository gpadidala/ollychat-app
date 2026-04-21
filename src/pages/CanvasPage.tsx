import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { config } from '@grafana/runtime';
import { IconButton, useStyles2 } from '@grafana/ui';
import { InvestigatePage } from './InvestigatePage';
import { SkillsPage } from './SkillsPage';
import { MCPConfigPage } from './MCPConfigPage';
import { RulesPage } from './RulesPage';
import { ConfigPage } from './ConfigPage';

type RightView = 'canvas' | 'investigate' | 'skills' | 'mcp' | 'rules' | 'settings';

interface ToolTab {
  id: RightView;
  label: string;
  icon: string;
  role: 'Viewer' | 'Editor' | 'Admin';
}

const TOOL_TABS: ToolTab[] = [
  { id: 'canvas', label: 'Canvas', icon: 'apps', role: 'Viewer' },
  { id: 'investigate', label: 'Investigate', icon: 'search', role: 'Viewer' },
  { id: 'skills', label: 'Skills', icon: 'book', role: 'Editor' },
  { id: 'mcp', label: 'MCP', icon: 'plug', role: 'Admin' },
  { id: 'rules', label: 'Rules', icon: 'shield', role: 'Editor' },
  { id: 'settings', label: 'Settings', icon: 'cog', role: 'Admin' },
];

const ROLE_RANK: Record<string, number> = { Viewer: 1, Editor: 2, Admin: 3 };

function canSeeTab(userRole: string, required: string): boolean {
  return (ROLE_RANK[userRole] ?? 1) >= (ROLE_RANK[required] ?? 3);
}

type EventKind =
  | 'intent_classified'
  | 'plan_proposed'
  | 'awaiting_approval'
  | 'action_committed'
  | 'error'
  | 'info'
  | 'user_message';

interface ReasoningEvent {
  type?: string;
  event: EventKind;
  session_id: string;
  trace_id?: string;
  seq: number;
  ts?: string;
  title: string;
  summary?: string;
  payload?: Record<string, any>;
  duration_ms?: number | null;
  requires_user_action?: boolean;
  human_action_options?: string[];
}

interface CardItem extends ReasoningEvent {
  localId: string;
  applied?: boolean;
  discarded?: boolean;
}

function orchestratorWsUrl(): string {
  const { hostname, protocol } = window.location;
  const wsProto = protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProto}//${hostname}:8000/api/v2/stream`;
}

function grafanaOriginForDashboard(): string {
  return `${window.location.protocol}//${window.location.host}`;
}

export function CanvasPage() {
  const styles = useStyles2(getStyles);
  const user = useMemo(() => config.bootData?.user?.login || 'anonymous', []);
  const role = useMemo(() => {
    const r = config.bootData?.user?.orgRole;
    return r && r.length ? r : 'Viewer';
  }, []);

  const [connState, setConnState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [iframeUrl, setIframeUrl] = useState<string | null>(null);
  const [iframeJustUpdated, setIframeJustUpdated] = useState(false);
  const [input, setInput] = useState('');
  const [rightView, setRightView] = useState<RightView>('canvas');

  const visibleTabs = useMemo(() => TOOL_TABS.filter((t) => canSeeTab(role, t.role)), [role]);

  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const currentDashUrlRef = useRef<string | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const url = `${orchestratorWsUrl()}?user=${encodeURIComponent(user)}&role=${encodeURIComponent(role)}`;
    let cancelled = false;
    let retry: number | undefined;

    const connect = () => {
      if (cancelled) {
        return;
      }
      setConnState('connecting');
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => setConnState('connected');
      ws.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data) as ReasoningEvent;
          if (ev.type && ev.type !== 'reasoning_event') {
            return;
          }
          setSessionId((prev) => prev || ev.session_id);
          setCards((prev) => [...prev, { ...ev, localId: `${ev.seq}-${ev.trace_id ?? ''}` }]);
          if (ev.event === 'action_committed' && ev.payload?.result?.url) {
            const path = ev.payload.result.url as string;
            const isSameDash = currentDashUrlRef.current === path;
            const bust = Date.now();
            const full = `${grafanaOriginForDashboard()}${path}?kiosk&theme=dark&_=${bust}`;
            currentDashUrlRef.current = path;
            setIframeUrl(full);
            setRightView('canvas');
            if (isSameDash) {
              setIframeJustUpdated(true);
              window.setTimeout(() => setIframeJustUpdated(false), 1500);
            }
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnState('disconnected');
        if (!cancelled) {
          retry = window.setTimeout(connect, 3000);
        }
      };
      ws.onerror = () => {
        /* onclose handles retry */
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (retry) {
        window.clearTimeout(retry);
      }
      wsRef.current?.close();
    };
  }, [user, role]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' });
  }, [cards]);

  const sendUserMessage = useCallback(() => {
    const text = input.trim();
    if (!text || !sessionId || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    setCards((prev) => [
      ...prev,
      {
        event: 'user_message',
        session_id: sessionId,
        seq: -Date.now(),
        title: 'You',
        summary: text,
        localId: `user-${Date.now()}`,
      },
    ]);
    wsRef.current.send(
      JSON.stringify({ type: 'user_message', session_id: sessionId, content: text, role })
    );
    setInput('');
  }, [input, role, sessionId]);

  const sendAction = useCallback(
    (verb: 'apply' | 'discard' | 'stop', targetSeq: number, localId: string) => {
      if (!wsRef.current || !sessionId) {
        return;
      }
      wsRef.current.send(
        JSON.stringify({ type: 'user_action', session_id: sessionId, verb, target_seq: targetSeq })
      );
      setCards((prev) =>
        prev.map((c) =>
          c.localId === localId ? { ...c, applied: verb === 'apply', discarded: verb === 'discard' } : c
        )
      );
    },
    [sessionId]
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape' && sessionId && wsRef.current) {
        wsRef.current.send(
          JSON.stringify({ type: 'user_action', session_id: sessionId, verb: 'discard' })
        );
      }
    },
    [sessionId]
  );

  return (
    <div className={styles.app} onKeyDown={onKeyDown}>
      <div className={styles.left}>
        <div className={styles.hdr}>
          <div>
            <h1 className={styles.title}>
              O11yBot Canvas <span className={styles.subtitle}>— Reasoning + Approvals</span>
            </h1>
            <div className={styles.sid}>
              {sessionId ? `session: ${sessionId.substring(0, 12)}…` : 'session: connecting…'}
            </div>
          </div>
          <div className={styles.status}>
            <span
              className={styles.dot}
              style={{
                background:
                  connState === 'connected' ? '#22c55e' : connState === 'connecting' ? '#f59e0b' : '#ef4444',
              }}
            />
            <span>{connState}</span>
          </div>
        </div>

        <div className={styles.feed} ref={feedRef}>
          {cards.length === 0 && (
            <div className={styles.empty}>
              Ask me to do anything — list firing alerts, explain a spike, or build a dashboard. Writes will
              pause for your approval.
            </div>
          )}
          {cards.map((c) => (
            <div key={c.localId} className={`${styles.card} ${styles[`card_${c.event}`] ?? ''}`}>
              <div className={styles.cardHdr}>
                <div>
                  <span className={styles.cardType}>{c.event}</span>
                  <span className={styles.cardTitle}>{c.title}</span>
                </div>
                <span className={styles.cardMeta}>
                  seq #{c.seq}
                  {c.duration_ms != null ? ` · ${c.duration_ms}ms` : ''}
                </span>
              </div>
              {c.summary && <div className={styles.cardBody}>{c.summary}</div>}
              {c.requires_user_action && !c.applied && !c.discarded && (
                <div className={styles.actions}>
                  <button
                    className={`${styles.btn} ${styles.btnApply}`}
                    onClick={() => sendAction('apply', c.seq, c.localId)}
                  >
                    ✓ Apply
                  </button>
                  <button
                    className={`${styles.btn} ${styles.btnDiscard}`}
                    onClick={() => sendAction('discard', c.seq, c.localId)}
                  >
                    ✗ Discard
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className={styles.composer}>
          <input
            className={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendUserMessage();
              }
            }}
            placeholder="e.g. create a latency dashboard for payment-service"
            disabled={connState !== 'connected'}
          />
          <button
            className={styles.sendBtn}
            onClick={sendUserMessage}
            disabled={connState !== 'connected' || !input.trim()}
          >
            Send
          </button>
        </div>
        <div className={styles.hint}>
          <strong>Writes require your approval.</strong> Read-only queries execute immediately. Press{' '}
          <kbd>Esc</kbd> to discard pending.
        </div>
      </div>

      <div className={styles.right}>
        <div className={styles.rightTabs}>
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              className={`${styles.tabBtn} ${rightView === tab.id ? styles.tabBtnActive : ''}`}
              onClick={() => setRightView(tab.id)}
              title={tab.label}
            >
              <IconButton name={tab.icon as any} size="md" aria-label={tab.label} tooltip={tab.label} />
              <span className={styles.tabLabel}>{tab.label}</span>
            </button>
          ))}
        </div>
        <div className={styles.rightBody}>
          {rightView === 'canvas' &&
            (iframeUrl ? (
              <>
                <iframe
                  ref={iframeRef}
                  className={styles.iframe}
                  src={iframeUrl}
                  title="Grafana canvas"
                />
                {iframeJustUpdated && <div className={styles.updateFlash}>✓ updated</div>}
              </>
            ) : (
              <div className={styles.rightEmpty}>
                <div>
                  <h2>Live Grafana canvas</h2>
                  <p>Ask OllyBot to build, edit, or explore dashboards — they render here as you iterate.</p>
                  <ul className={styles.welcomeTips}>
                    <li>
                      Try: <em>&ldquo;create a latency dashboard for payment-service&rdquo;</em>
                    </li>
                    <li>
                      Then: <em>&ldquo;add error-rate and p99 panels&rdquo;</em>
                    </li>
                    <li>
                      Or: <em>&ldquo;list firing alerts&rdquo;</em> /{' '}
                      <em>&ldquo;show Loki logs for checkout&rdquo;</em>
                    </li>
                  </ul>
                </div>
              </div>
            ))}
          {rightView === 'investigate' && <InvestigatePage />}
          {rightView === 'skills' && <SkillsPage />}
          {rightView === 'mcp' && <MCPConfigPage />}
          {rightView === 'rules' && <RulesPage />}
          {rightView === 'settings' && <ConfigPage />}
        </div>
      </div>
    </div>
  );
}

const getStyles = (theme: GrafanaTheme2) => ({
  app: css`
    display: grid;
    grid-template-columns: 40% 60%;
    height: calc(100vh - 80px);
    min-height: 600px;
    gap: 0;
    background: ${theme.colors.background.primary};
  `,
  left: css`
    display: flex;
    flex-direction: column;
    border-right: 1px solid ${theme.colors.border.weak};
    background: ${theme.colors.background.secondary};
    min-width: 0;
  `,
  hdr: css`
    padding: ${theme.spacing(1.5, 2)};
    border-bottom: 1px solid ${theme.colors.border.weak};
    display: flex;
    justify-content: space-between;
    align-items: center;
  `,
  title: css`
    font-size: 15px;
    font-weight: 700;
    color: ${theme.colors.text.primary};
    margin: 0;
  `,
  subtitle: css`
    color: ${theme.colors.text.secondary};
    font-weight: 400;
  `,
  sid: css`
    font-family: ${theme.typography.fontFamilyMonospace};
    font-size: 11px;
    color: ${theme.colors.text.secondary};
    margin-top: 2px;
  `,
  status: css`
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: ${theme.colors.text.secondary};
  `,
  dot: css`
    width: 8px;
    height: 8px;
    border-radius: 50%;
  `,
  feed: css`
    flex: 1;
    overflow-y: auto;
    padding: ${theme.spacing(1.5, 2)};
  `,
  empty: css`
    color: ${theme.colors.text.secondary};
    text-align: center;
    padding: ${theme.spacing(6, 2)};
    font-size: 13px;
  `,
  card: css`
    margin-bottom: ${theme.spacing(1)};
    padding: ${theme.spacing(1.25, 1.5)};
    border-radius: ${theme.shape.radius.default};
    background: ${theme.colors.background.primary};
    border: 1px solid ${theme.colors.border.weak};
    border-left-width: 3px;
    border-left-color: ${theme.colors.border.medium};
  `,
  card_intent_classified: css`
    border-left-color: #a78bfa;
  `,
  card_plan_proposed: css`
    border-left-color: #06b6d4;
  `,
  card_awaiting_approval: css`
    border-left-color: #f59e0b;
  `,
  card_action_committed: css`
    border-left-color: #22c55e;
  `,
  card_error: css`
    border-left-color: #ef4444;
  `,
  card_info: css`
    border-left-color: ${theme.colors.border.medium};
  `,
  card_user_message: css`
    border-left-color: ${theme.colors.primary.main};
    background: ${theme.colors.background.canvas};
  `,
  cardHdr: css`
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 4px;
    gap: 8px;
  `,
  cardType: css`
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 10px;
    background: ${theme.colors.background.canvas};
    color: ${theme.colors.text.secondary};
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
    margin-right: 8px;
  `,
  cardTitle: css`
    font-weight: 600;
    color: ${theme.colors.text.primary};
    font-size: 13px;
  `,
  cardMeta: css`
    font-size: 10px;
    color: ${theme.colors.text.secondary};
    font-family: ${theme.typography.fontFamilyMonospace};
    white-space: nowrap;
  `,
  cardBody: css`
    font-size: 13px;
    color: ${theme.colors.text.primary};
    white-space: pre-wrap;
    word-wrap: break-word;
  `,
  actions: css`
    display: flex;
    gap: 8px;
    margin-top: ${theme.spacing(1)};
  `,
  btn: css`
    padding: 6px 14px;
    border: none;
    border-radius: ${theme.shape.radius.default};
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  `,
  btnApply: css`
    background: #22c55e;
    color: #fff;
    &:hover {
      filter: brightness(1.1);
    }
  `,
  btnDiscard: css`
    background: ${theme.colors.background.canvas};
    color: ${theme.colors.text.primary};
    border: 1px solid ${theme.colors.border.medium};
    &:hover {
      background: ${theme.colors.background.secondary};
    }
  `,
  composer: css`
    padding: ${theme.spacing(1.5, 2, 0.5, 2)};
    border-top: 1px solid ${theme.colors.border.weak};
    display: flex;
    gap: 8px;
  `,
  input: css`
    flex: 1;
    padding: 8px 12px;
    background: ${theme.colors.background.primary};
    border: 1px solid ${theme.colors.border.medium};
    border-radius: ${theme.shape.radius.default};
    color: ${theme.colors.text.primary};
    font-family: inherit;
    font-size: 13px;
    outline: none;
    &:focus {
      border-color: ${theme.colors.primary.main};
    }
  `,
  sendBtn: css`
    padding: 8px 18px;
    background: ${theme.colors.primary.main};
    color: ${theme.colors.primary.contrastText};
    border: none;
    border-radius: ${theme.shape.radius.default};
    font-weight: 600;
    cursor: pointer;
    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  `,
  hint: css`
    padding: ${theme.spacing(0.5, 2, 1.5, 2)};
    font-size: 11px;
    color: ${theme.colors.text.secondary};
  `,
  right: css`
    background: ${theme.colors.background.canvas};
    position: relative;
    min-width: 0;
    display: flex;
    flex-direction: column;
  `,
  rightTabs: css`
    display: flex;
    gap: 2px;
    padding: ${theme.spacing(0.5, 1, 0, 1)};
    background: ${theme.colors.background.secondary};
    border-bottom: 1px solid ${theme.colors.border.weak};
    overflow-x: auto;
  `,
  tabBtn: css`
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: ${theme.spacing(0.75, 1.25)};
    background: transparent;
    border: 0;
    color: ${theme.colors.text.secondary};
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    &:hover {
      color: ${theme.colors.text.primary};
      background: ${theme.colors.background.primary};
    }
  `,
  tabBtnActive: css`
    color: ${theme.colors.text.primary};
    border-bottom-color: ${theme.colors.primary.main};
    background: ${theme.colors.background.primary};
  `,
  tabLabel: css`
    display: inline-block;
  `,
  rightBody: css`
    flex: 1;
    position: relative;
    overflow: auto;
    min-height: 0;
  `,
  rightEmpty: css`
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: ${theme.colors.text.secondary};
    font-size: 14px;
    text-align: center;
    padding: ${theme.spacing(4)};
    h2 {
      color: ${theme.colors.text.primary};
      margin-bottom: 8px;
      font-size: 18px;
    }
  `,
  welcomeTips: css`
    list-style: none;
    padding: 0;
    margin: ${theme.spacing(2, 0, 0, 0)};
    text-align: left;
    display: inline-block;
    li {
      padding: ${theme.spacing(0.75, 0)};
      font-size: 13px;
      color: ${theme.colors.text.secondary};
      em {
        font-style: normal;
        color: ${theme.colors.text.primary};
        background: ${theme.colors.background.secondary};
        padding: 2px 6px;
        border-radius: 3px;
        font-family: ${theme.typography.fontFamilyMonospace};
        font-size: 12px;
      }
    }
  `,
  iframe: css`
    width: 100%;
    height: 100%;
    border: 0;
    background: ${theme.colors.background.canvas};
  `,
  updateFlash: css`
    position: absolute;
    top: 12px;
    right: 16px;
    background: #22c55e;
    color: #fff;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    box-shadow: 0 4px 12px rgba(34, 197, 94, 0.4);
    animation: fade 1.5s ease;
    pointer-events: none;
    @keyframes fade {
      0%, 70% { opacity: 1; transform: translateY(0); }
      100% { opacity: 0; transform: translateY(-4px); }
    }
  `,
});
