import React, { useCallback, useRef, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Button, TextArea, useStyles2 } from '@grafana/ui';
import { MAX_MESSAGE_LENGTH } from '../constants';

interface Props {
  onSend: (message: string) => void;
  isStreaming: boolean;
  onStop: () => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, isStreaming, onStop, disabled }: Props) {
  const styles = useStyles2(getStyles);
  const [input, setInput] = useState('');
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    onSend(trimmed);
    setInput('');
    textAreaRef.current?.focus();
  }, [input, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className={styles.container}>
      <TextArea
        ref={textAreaRef}
        className={styles.textarea}
        value={input}
        onChange={(e) => setInput(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
        placeholder={isStreaming ? 'Waiting for response...' : 'Ask about your infrastructure, metrics, or incidents...'}
        rows={1}
        maxLength={MAX_MESSAGE_LENGTH}
        disabled={disabled || isStreaming}
      />
      <div className={styles.actions}>
        {isStreaming ? (
          <Button variant="destructive" size="sm" icon="square-shape" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            icon="arrow-right"
            onClick={handleSend}
            disabled={!input.trim() || disabled}
          >
            Send
          </Button>
        )}
        <span className={styles.charCount}>
          {input.length}/{MAX_MESSAGE_LENGTH}
        </span>
      </div>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({
      padding: theme.spacing(2),
      borderTop: `1px solid ${theme.colors.border.weak}`,
      background: theme.colors.background.primary,
    }),
    textarea: css({
      resize: 'none',
      width: '100%',
      minHeight: '44px',
      maxHeight: '200px',
      marginBottom: theme.spacing(1),
    }),
    actions: css({
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
    }),
    charCount: css({
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.disabled,
    }),
  };
}
