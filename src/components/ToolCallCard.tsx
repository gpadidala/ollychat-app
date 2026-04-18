import React, { useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Badge, Button, Collapse, Icon, useStyles2 } from '@grafana/ui';
import { ToolCall } from '../types';

interface Props {
  toolCall: ToolCall;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
}

export function ToolCallCard({ toolCall, onApprove, onReject }: Props) {
  const styles = useStyles2(getStyles);
  const [expanded, setExpanded] = useState(false);

  const statusColor: Record<string, 'blue' | 'green' | 'red' | 'orange' | 'purple'> = {
    pending: 'orange',
    approved: 'blue',
    running: 'blue',
    complete: 'green',
    error: 'red',
    rejected: 'purple',
  };

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <Icon name="plug" size="sm" />
        <span className={styles.toolName}>{toolCall.name}</span>
        <Badge text={toolCall.status} color={statusColor[toolCall.status] ?? 'blue'} />
        {toolCall.durationMs !== undefined && (
          <span className={styles.duration}>{toolCall.durationMs}ms</span>
        )}
      </div>

      {/* Approval buttons for pending tool calls */}
      {toolCall.status === 'pending' && onApprove && onReject && (
        <div className={styles.approvalRow}>
          <Button size="sm" variant="primary" icon="check" onClick={() => onApprove(toolCall.id)}>
            Approve
          </Button>
          <Button size="sm" variant="destructive" icon="times" onClick={() => onReject(toolCall.id)}>
            Reject
          </Button>
        </div>
      )}

      {/* Arguments */}
      <Collapse label="Arguments" isOpen={expanded} onToggle={() => setExpanded(!expanded)} collapsible>
        <pre className={styles.json}>
          {JSON.stringify(toolCall.arguments, null, 2)}
        </pre>
      </Collapse>

      {/* Result */}
      {toolCall.result !== undefined && (
        <Collapse label="Result" isOpen={false} collapsible>
          <pre className={styles.json}>
            {typeof toolCall.result === 'string'
              ? toolCall.result
              : JSON.stringify(toolCall.result, null, 2)?.slice(0, 5000)}
          </pre>
        </Collapse>
      )}

      {/* Error */}
      {toolCall.error && (
        <div className={styles.error}>
          <Icon name="exclamation-triangle" size="sm" />
          {toolCall.error}
        </div>
      )}
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    card: css({
      border: `1px solid ${theme.colors.border.medium}`,
      borderRadius: theme.shape.radius.default,
      padding: theme.spacing(1.5),
      margin: theme.spacing(1, 0),
      background: theme.colors.background.canvas,
    }),
    header: css({
      display: 'flex',
      alignItems: 'center',
      gap: theme.spacing(1),
      marginBottom: theme.spacing(1),
    }),
    toolName: css({
      fontFamily: theme.typography.fontFamilyMonospace,
      fontWeight: theme.typography.fontWeightMedium,
      fontSize: theme.typography.bodySmall.fontSize,
    }),
    duration: css({
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.secondary,
      marginLeft: 'auto',
    }),
    approvalRow: css({
      display: 'flex',
      gap: theme.spacing(1),
      margin: theme.spacing(1, 0),
    }),
    json: css({
      background: theme.colors.background.primary,
      padding: theme.spacing(1),
      borderRadius: theme.shape.radius.default,
      fontSize: '12px',
      fontFamily: theme.typography.fontFamilyMonospace,
      overflow: 'auto',
      maxHeight: 300,
      margin: 0,
    }),
    error: css({
      display: 'flex',
      alignItems: 'center',
      gap: theme.spacing(0.5),
      color: theme.colors.error.text,
      fontSize: theme.typography.bodySmall.fontSize,
      marginTop: theme.spacing(1),
    }),
  };
}
