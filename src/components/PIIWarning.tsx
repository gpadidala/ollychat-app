import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Alert, Button, useStyles2 } from '@grafana/ui';
import { PIIDetection } from '../types';

interface Props {
  detections: PIIDetection[];
  originalText: string;
  onSendAnyway: () => void;
  onRedactAndSend: (redactedText: string) => void;
  onCancel: () => void;
}

export function PIIWarning({ detections, originalText, onSendAnyway, onRedactAndSend, onCancel }: Props) {
  const styles = useStyles2(getStyles);

  const redactedText = redactPII(originalText, detections);
  const piiTypes = [...new Set(detections.map((d) => d.type))];

  return (
    <div className={styles.container}>
      <Alert title="PII Detected" severity="warning">
        <p>
          The following sensitive information was detected in your message:
          <strong> {piiTypes.join(', ')}</strong>
        </p>
        <div className={styles.preview}>
          <div className={styles.previewLabel}>Original:</div>
          <div className={styles.previewText}>{highlightPII(originalText, detections)}</div>
        </div>
        <div className={styles.preview}>
          <div className={styles.previewLabel}>Redacted:</div>
          <div className={styles.previewText}>{redactedText}</div>
        </div>
        <div className={styles.actions}>
          <Button variant="primary" size="sm" onClick={() => onRedactAndSend(redactedText)}>
            Redact &amp; Send
          </Button>
          <Button variant="secondary" size="sm" onClick={onSendAnyway}>
            Send Anyway
          </Button>
          <Button variant="destructive" size="sm" fill="text" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </Alert>
    </div>
  );
}

function redactPII(text: string, detections: PIIDetection[]): string {
  // Sort by start position descending to preserve indices
  const sorted = [...detections].sort((a, b) => b.start - a.start);
  let result = text;
  for (const d of sorted) {
    result = result.slice(0, d.start) + `[${d.type.toUpperCase()}_REDACTED]` + result.slice(d.end);
  }
  return result;
}

function highlightPII(text: string, detections: PIIDetection[]): React.ReactNode {
  if (detections.length === 0) {
    return text;
  }

  const sorted = [...detections].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let lastEnd = 0;

  for (const d of sorted) {
    if (d.start > lastEnd) {
      parts.push(text.slice(lastEnd, d.start));
    }
    parts.push(
      <mark key={d.start} style={{ background: '#ef444466', borderRadius: 2, padding: '0 2px' }}>
        {text.slice(d.start, d.end)}
      </mark>
    );
    lastEnd = d.end;
  }
  if (lastEnd < text.length) {
    parts.push(text.slice(lastEnd));
  }
  return <>{parts}</>;
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({
      margin: theme.spacing(1, 0),
    }),
    preview: css({
      margin: theme.spacing(1, 0),
    }),
    previewLabel: css({
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.secondary,
      marginBottom: theme.spacing(0.5),
    }),
    previewText: css({
      fontFamily: theme.typography.fontFamilyMonospace,
      fontSize: theme.typography.bodySmall.fontSize,
      padding: theme.spacing(1),
      background: theme.colors.background.canvas,
      borderRadius: theme.shape.radius.default,
      wordBreak: 'break-all',
    }),
    actions: css({
      display: 'flex',
      gap: theme.spacing(1),
      marginTop: theme.spacing(1.5),
    }),
  };
}
