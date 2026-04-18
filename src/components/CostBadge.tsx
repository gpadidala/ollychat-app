import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Tooltip, useStyles2 } from '@grafana/ui';
import { TokenUsage } from '../types';

interface Props {
  costUsd?: number;
  usage?: TokenUsage;
}

export function CostBadge({ costUsd, usage }: Props) {
  const styles = useStyles2(getStyles);

  if (costUsd === undefined || costUsd <= 0) {
    return null;
  }

  const colorClass =
    costUsd < 0.01 ? styles.low :
    costUsd < 0.10 ? styles.medium :
    styles.high;

  const tooltipContent = usage
    ? `Input: ${usage.promptTokens.toLocaleString()} tokens\nOutput: ${usage.completionTokens.toLocaleString()} tokens\nTotal: ${usage.totalTokens.toLocaleString()} tokens\nCost: $${costUsd.toFixed(6)}`
    : `Cost: $${costUsd.toFixed(6)}`;

  return (
    <Tooltip content={tooltipContent} placement="top">
      <span className={`${styles.badge} ${colorClass}`}>
        ${costUsd < 0.001 ? costUsd.toFixed(5) : costUsd.toFixed(4)}
      </span>
    </Tooltip>
  );
}

export function SessionCostTracker({ totalCost, messageCount }: { totalCost: number; messageCount: number }) {
  const styles = useStyles2(getStyles);

  if (totalCost <= 0) {
    return null;
  }

  return (
    <Tooltip content={`${messageCount} messages | Avg: $${(totalCost / Math.max(messageCount, 1)).toFixed(5)}/msg`}>
      <span className={styles.sessionCost}>
        Session: ${totalCost.toFixed(4)}
      </span>
    </Tooltip>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    badge: css({
      display: 'inline-block',
      padding: '1px 6px',
      borderRadius: theme.shape.radius.pill,
      fontSize: '11px',
      fontFamily: theme.typography.fontFamilyMonospace,
      fontWeight: theme.typography.fontWeightMedium,
    }),
    low: css({
      background: theme.colors.success.transparent,
      color: theme.colors.success.text,
    }),
    medium: css({
      background: theme.colors.warning.transparent,
      color: theme.colors.warning.text,
    }),
    high: css({
      background: theme.colors.error.transparent,
      color: theme.colors.error.text,
    }),
    sessionCost: css({
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.warning.text,
      fontFamily: theme.typography.fontFamilyMonospace,
    }),
  };
}
