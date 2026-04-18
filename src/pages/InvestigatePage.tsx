import React, { useCallback, useEffect, useRef, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import {
  Alert,
  Badge,
  Button,
  Field,
  Icon,
  Input,
  Tab,
  TabContent,
  TabsBar,
  TextArea,
  useStyles2,
} from '@grafana/ui';
import ReactMarkdown from 'react-markdown';
import { API } from '../constants';
import { Hypothesis, Investigation, Observation } from '../types';

type TabKey = 'summary' | 'report' | 'timeline' | 'activity';

export function InvestigatePage() {
  const styles = useStyles2(getStyles);
  const [activeTab, setActiveTab] = useState<TabKey>('summary');
  const [prompt, setPrompt] = useState('');
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const activityEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    activityEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activityLog]);

  const launchInvestigation = useCallback(async () => {
    if (!prompt.trim()) return;
    setIsRunning(true);
    setActivityLog([]);
    setInvestigation(null);
    setActiveTab('activity');

    try {
      const response = await fetch(API.INVESTIGATE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: prompt, stream: true }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Investigation failed: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const dataLine = frame.split('\n').find((l) => l.startsWith('data: '));
          if (!dataLine) continue;
          const jsonStr = dataLine.slice(6);
          if (jsonStr === '[DONE]') continue;

          try {
            const event = JSON.parse(jsonStr);
            if (event.type === 'progress') {
              setActivityLog((prev) => [...prev, event.message]);
            } else if (event.type === 'tool_call') {
              setActivityLog((prev) => [...prev, `Tool: ${event.tool} | ${JSON.stringify(event.args).slice(0, 200)}`]);
            } else if (event.type === 'tool_result') {
              setActivityLog((prev) => [...prev, `Result (${event.duration_ms}ms): ${JSON.stringify(event.result).slice(0, 300)}`]);
            } else if (event.type === 'hypothesis') {
              setActivityLog((prev) => [...prev, `Hypothesis: ${event.pattern} (${event.confidence}% confidence)`]);
            } else if (event.type === 'complete') {
              setInvestigation(event.investigation);
              setActiveTab('summary');
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err) {
      setActivityLog((prev) => [...prev, `ERROR: ${err instanceof Error ? err.message : String(err)}`]);
    } finally {
      setIsRunning(false);
    }
  }, [prompt]);

  const confidenceColor = (c: number) =>
    c >= 80 ? 'green' : c >= 50 ? 'orange' : 'red';

  return (
    <div className={styles.container}>
      {/* Launch Bar */}
      <div className={styles.launchBar}>
        <h3>Investigation Engine</h3>
        <div className={styles.launchRow}>
          <Input
            className={styles.promptInput}
            value={prompt}
            onChange={(e) => setPrompt(e.currentTarget.value)}
            placeholder="Describe the incident: e.g. High latency in payment-service since 2pm..."
            onKeyDown={(e) => e.key === 'Enter' && launchInvestigation()}
          />
          <Button
            variant="primary"
            icon={isRunning ? 'fa fa-spinner' : 'search'}
            onClick={launchInvestigation}
            disabled={isRunning || !prompt.trim()}
          >
            {isRunning ? 'Investigating...' : 'Investigate'}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      {(investigation || activityLog.length > 0) && (
        <>
          <TabsBar>
            <Tab label="Summary" active={activeTab === 'summary'} onChangeTab={() => setActiveTab('summary')}
              icon="info-circle" counter={investigation?.hypotheses?.length} />
            <Tab label="Report" active={activeTab === 'report'} onChangeTab={() => setActiveTab('report')} icon="file-alt" />
            <Tab label="Timeline" active={activeTab === 'timeline'} onChangeTab={() => setActiveTab('timeline')}
              icon="clock-nine" counter={investigation?.observations?.length} />
            <Tab label="Activity" active={activeTab === 'activity'} onChangeTab={() => setActiveTab('activity')}
              icon="list-ul" counter={activityLog.length} />
          </TabsBar>

          <TabContent className={styles.tabContent}>
            {/* Summary Tab */}
            {activeTab === 'summary' && investigation && (
              <div className={styles.summary}>
                <div className={styles.summaryGrid}>
                  <div className={styles.summaryCard}>
                    <h5>Root Cause</h5>
                    <p>{investigation.rootCause ?? 'Still investigating...'}</p>
                  </div>
                  <div className={styles.summaryCard}>
                    <h5>Confidence</h5>
                    <Badge
                      text={`${investigation.confidence}%`}
                      color={confidenceColor(investigation.confidence)}
                    />
                  </div>
                  <div className={styles.summaryCard}>
                    <h5>Impact</h5>
                    <p>{investigation.impact ?? 'Unknown'}</p>
                  </div>
                  <div className={styles.summaryCard}>
                    <h5>Affected Services</h5>
                    <div className={styles.tagList}>
                      {investigation.affectedServices.map((s) => (
                        <Badge key={s} text={s} color="blue" />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Hypotheses */}
                {investigation.hypotheses.length > 0 && (
                  <div className={styles.section}>
                    <h4>Hypotheses</h4>
                    {investigation.hypotheses.map((h, i) => (
                      <div key={i} className={styles.hypothesisCard}>
                        <div className={styles.hypothesisHeader}>
                          <span className={styles.rank}>#{h.rank}</span>
                          <strong>{h.pattern}</strong>
                          <Badge text={`${h.confidence}%`} color={confidenceColor(h.confidence)} />
                        </div>
                        <p className={styles.impact}>{h.impact}</p>
                        <div className={styles.evidenceList}>
                          {h.evidence.map((e, j) => (
                            <div key={j} className={styles.evidence}>
                              <Icon name="check-circle" size="sm" /> {e}
                            </div>
                          ))}
                        </div>
                        {h.remediation && (
                          <div className={styles.remediation}>
                            <strong>Remediation:</strong> {h.remediation}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Recommended Actions */}
                {investigation.recommendedActions.length > 0 && (
                  <div className={styles.section}>
                    <h4>Recommended Actions</h4>
                    <ol>
                      {investigation.recommendedActions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}

            {/* Report Tab */}
            {activeTab === 'report' && (
              <div className={styles.report}>
                {investigation?.report ? (
                  <ReactMarkdown>{investigation.report}</ReactMarkdown>
                ) : (
                  <p className={styles.placeholder}>Report will be generated after investigation completes.</p>
                )}
              </div>
            )}

            {/* Timeline Tab */}
            {activeTab === 'timeline' && (
              <div className={styles.timeline}>
                {(investigation?.observations ?? []).map((obs, i) => (
                  <div key={i} className={styles.timelineItem}>
                    <div className={styles.timelineDot}>
                      <Icon name={obs.ok ? 'check-circle' : 'exclamation-triangle'} size="sm" />
                    </div>
                    <div className={styles.timelineContent}>
                      <div className={styles.timelineHeader}>
                        <strong>{obs.tool}</strong>
                        <Badge text={obs.ok ? 'success' : 'error'} color={obs.ok ? 'green' : 'red'} />
                      </div>
                      <pre className={styles.timelineArgs}>{JSON.stringify(obs.args, null, 2)}</pre>
                      {obs.error && <Alert title="Error" severity="error">{obs.error}</Alert>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Activity Tab */}
            {activeTab === 'activity' && (
              <div className={styles.activity}>
                {activityLog.map((msg, i) => (
                  <div key={i} className={styles.activityLine}>
                    <span className={styles.activityIdx}>{i + 1}</span>
                    <span>{msg}</span>
                  </div>
                ))}
                {isRunning && <div className={styles.activityLine}><Icon name="fa fa-spinner" /> Running...</div>}
                <div ref={activityEndRef} />
              </div>
            )}
          </TabContent>
        </>
      )}
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({ padding: theme.spacing(3), maxWidth: 1200 }),
    launchBar: css({ marginBottom: theme.spacing(3) }),
    launchRow: css({ display: 'flex', gap: theme.spacing(1), marginTop: theme.spacing(1) }),
    promptInput: css({ flex: 1 }),
    tabContent: css({ padding: theme.spacing(2, 0) }),
    summary: css({}),
    summaryGrid: css({
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: theme.spacing(2), marginBottom: theme.spacing(3),
    }),
    summaryCard: css({
      padding: theme.spacing(2), background: theme.colors.background.secondary,
      border: `1px solid ${theme.colors.border.weak}`, borderRadius: theme.shape.radius.default,
      '& h5': { margin: 0, marginBottom: theme.spacing(0.5), color: theme.colors.text.secondary, fontSize: theme.typography.bodySmall.fontSize },
    }),
    tagList: css({ display: 'flex', flexWrap: 'wrap', gap: theme.spacing(0.5) }),
    section: css({ marginBottom: theme.spacing(3), '& h4': { marginBottom: theme.spacing(1) } }),
    hypothesisCard: css({
      padding: theme.spacing(2), background: theme.colors.background.secondary,
      border: `1px solid ${theme.colors.border.weak}`, borderRadius: theme.shape.radius.default, marginBottom: theme.spacing(1),
    }),
    hypothesisHeader: css({ display: 'flex', alignItems: 'center', gap: theme.spacing(1), marginBottom: theme.spacing(1) }),
    rank: css({ color: theme.colors.text.secondary, fontWeight: theme.typography.fontWeightBold }),
    impact: css({ color: theme.colors.text.secondary, margin: theme.spacing(0.5, 0) }),
    evidenceList: css({ marginTop: theme.spacing(1) }),
    evidence: css({
      display: 'flex', alignItems: 'center', gap: theme.spacing(0.5),
      fontSize: theme.typography.bodySmall.fontSize, color: theme.colors.text.secondary, marginBottom: 2,
    }),
    remediation: css({ marginTop: theme.spacing(1), padding: theme.spacing(1), background: theme.colors.success.transparent, borderRadius: theme.shape.radius.default }),
    report: css({
      '& pre': { background: theme.colors.background.canvas, padding: theme.spacing(1.5), borderRadius: theme.shape.radius.default, overflow: 'auto' },
      '& table': { width: '100%', borderCollapse: 'collapse', '& th, & td': { border: `1px solid ${theme.colors.border.medium}`, padding: theme.spacing(0.5, 1) } },
    }),
    placeholder: css({ color: theme.colors.text.secondary, fontStyle: 'italic' }),
    timeline: css({ position: 'relative', paddingLeft: theme.spacing(4) }),
    timelineItem: css({
      display: 'flex', gap: theme.spacing(1.5), marginBottom: theme.spacing(2), position: 'relative',
      '&::before': { content: '""', position: 'absolute', left: -24, top: 20, bottom: -16, width: 2, background: theme.colors.border.weak },
    }),
    timelineDot: css({
      position: 'absolute', left: -32, width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: theme.colors.background.primary, border: `2px solid ${theme.colors.border.medium}`, borderRadius: '50%', zIndex: 1,
    }),
    timelineContent: css({ flex: 1, paddingLeft: theme.spacing(1) }),
    timelineHeader: css({ display: 'flex', alignItems: 'center', gap: theme.spacing(1), marginBottom: theme.spacing(0.5) }),
    timelineArgs: css({
      fontSize: '11px', fontFamily: theme.typography.fontFamilyMonospace, background: theme.colors.background.canvas,
      padding: theme.spacing(0.5, 1), borderRadius: theme.shape.radius.default, margin: 0, maxHeight: 150, overflow: 'auto',
    }),
    activity: css({ fontFamily: theme.typography.fontFamilyMonospace, fontSize: '13px' }),
    activityLine: css({
      display: 'flex', gap: theme.spacing(1), padding: theme.spacing(0.5, 1),
      borderBottom: `1px solid ${theme.colors.border.weak}`, '&:hover': { background: theme.colors.action.hover },
    }),
    activityIdx: css({ color: theme.colors.text.disabled, minWidth: 30, textAlign: 'right' }),
  };
}
