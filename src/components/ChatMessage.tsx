import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Icon, Spinner, useStyles2 } from '@grafana/ui';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage as ChatMessageType } from '../types';

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const styles = useStyles2(getStyles);
  const isUser = message.role === 'user';

  return (
    <div className={isUser ? styles.userRow : styles.assistantRow}>
      <div className={styles.avatar}>
        <Icon name={isUser ? 'user' : 'brain'} size="lg" />
      </div>
      <div className={isUser ? styles.userBubble : styles.assistantBubble}>
        <div className={styles.content}>
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          )}
          {message.isStreaming && <Spinner className={styles.cursor} size="sm" />}
        </div>
        <div className={styles.meta}>
          {message.model && <span className={styles.model}>{message.model}</span>}
          {message.usage && (
            <span className={styles.tokens}>
              {message.usage.totalTokens} tokens
            </span>
          )}
          {message.costUsd !== undefined && message.costUsd > 0 && (
            <span className={styles.cost}>${message.costUsd.toFixed(4)}</span>
          )}
          <span className={styles.time}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  const bubbleBase = css({
    maxWidth: '80%',
    padding: theme.spacing(1.5, 2),
    borderRadius: theme.shape.radius.default,
    wordBreak: 'break-word',
    '& pre': {
      background: theme.colors.background.canvas,
      padding: theme.spacing(1),
      borderRadius: theme.shape.radius.default,
      overflow: 'auto',
      fontSize: theme.typography.bodySmall.fontSize,
    },
    '& code': {
      fontSize: theme.typography.bodySmall.fontSize,
      background: theme.colors.background.canvas,
      padding: '2px 4px',
      borderRadius: '3px',
    },
    '& pre code': {
      background: 'none',
      padding: 0,
    },
    '& table': {
      width: '100%',
      borderCollapse: 'collapse',
      '& th, & td': {
        border: `1px solid ${theme.colors.border.medium}`,
        padding: theme.spacing(0.5, 1),
        textAlign: 'left',
      },
      '& th': {
        background: theme.colors.background.canvas,
      },
    },
    '& blockquote': {
      borderLeft: `3px solid ${theme.colors.primary.border}`,
      margin: theme.spacing(1, 0),
      padding: theme.spacing(0.5, 1.5),
      color: theme.colors.text.secondary,
    },
  });

  return {
    userRow: css({
      display: 'flex',
      justifyContent: 'flex-end',
      gap: theme.spacing(1),
      marginBottom: theme.spacing(2),
    }),
    assistantRow: css({
      display: 'flex',
      justifyContent: 'flex-start',
      gap: theme.spacing(1),
      marginBottom: theme.spacing(2),
    }),
    avatar: css({
      width: 32,
      height: 32,
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      background: theme.colors.background.canvas,
      border: `1px solid ${theme.colors.border.weak}`,
    }),
    userBubble: css(bubbleBase, {
      background: theme.colors.primary.shade,
      border: `1px solid ${theme.colors.primary.border}`,
    }),
    assistantBubble: css(bubbleBase, {
      background: theme.colors.background.secondary,
      border: `1px solid ${theme.colors.border.weak}`,
    }),
    content: css({
      '& p:first-child': { marginTop: 0 },
      '& p:last-child': { marginBottom: 0 },
      lineHeight: 1.6,
    }),
    cursor: css({
      display: 'inline-block',
      marginLeft: theme.spacing(0.5),
    }),
    meta: css({
      display: 'flex',
      gap: theme.spacing(1.5),
      marginTop: theme.spacing(1),
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.secondary,
    }),
    model: css({
      color: theme.colors.text.disabled,
    }),
    tokens: css({
      color: theme.colors.text.disabled,
    }),
    cost: css({
      color: theme.colors.warning.text,
      fontWeight: theme.typography.fontWeightMedium,
    }),
    time: css({
      color: theme.colors.text.disabled,
    }),
  };
}
