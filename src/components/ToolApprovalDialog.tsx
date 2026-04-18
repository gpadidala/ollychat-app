import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Button, Icon, Modal, useStyles2 } from '@grafana/ui';
import { ToolCall } from '../types';

interface Props {
  toolCall: ToolCall;
  isOpen: boolean;
  onApprove: () => void;
  onReject: () => void;
  onAlwaysAllow?: () => void;
}

export function ToolApprovalDialog({ toolCall, isOpen, onApprove, onReject, onAlwaysAllow }: Props) {
  const styles = useStyles2(getStyles);

  return (
    <Modal title="Tool Call Approval" isOpen={isOpen} onDismiss={onReject}>
      <div className={styles.content}>
        <div className={styles.infoRow}>
          <Icon name="plug" size="lg" />
          <div>
            <h5 className={styles.toolName}>{toolCall.name}</h5>
            <p className={styles.description}>
              The assistant wants to execute this MCP tool. Review the arguments below and approve or reject.
            </p>
          </div>
        </div>

        <div className={styles.section}>
          <h6>Arguments</h6>
          <pre className={styles.json}>
            {JSON.stringify(toolCall.arguments, null, 2)}
          </pre>
        </div>

        <div className={styles.actions}>
          <Button variant="primary" icon="check" onClick={onApprove}>
            Approve
          </Button>
          <Button variant="destructive" icon="times" onClick={onReject}>
            Reject
          </Button>
          {onAlwaysAllow && (
            <Button variant="secondary" icon="shield" onClick={onAlwaysAllow}>
              Always Allow
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    content: css({
      display: 'flex',
      flexDirection: 'column',
      gap: theme.spacing(2),
    }),
    infoRow: css({
      display: 'flex',
      gap: theme.spacing(2),
      alignItems: 'flex-start',
    }),
    toolName: css({
      margin: 0,
      fontFamily: theme.typography.fontFamilyMonospace,
    }),
    description: css({
      color: theme.colors.text.secondary,
      margin: theme.spacing(0.5, 0, 0),
    }),
    section: css({
      '& h6': { marginBottom: theme.spacing(0.5) },
    }),
    json: css({
      background: theme.colors.background.canvas,
      padding: theme.spacing(1.5),
      borderRadius: theme.shape.radius.default,
      fontSize: '12px',
      fontFamily: theme.typography.fontFamilyMonospace,
      overflow: 'auto',
      maxHeight: 300,
      margin: 0,
    }),
    actions: css({
      display: 'flex',
      gap: theme.spacing(1),
      justifyContent: 'flex-end',
      paddingTop: theme.spacing(1),
      borderTop: `1px solid ${theme.colors.border.weak}`,
    }),
  };
}
