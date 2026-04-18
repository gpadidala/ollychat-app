import React, { useCallback, useEffect, useRef, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Alert, useStyles2 } from '@grafana/ui';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { ConversationSidebar } from '../components/ConversationSidebar';
import { ModelSelector } from '../components/ModelSelector';
import { useChat } from '../hooks/useChat';
import { DEFAULT_SETTINGS } from '../types';

export function ChatPage() {
  const styles = useStyles2(getStyles);
  const [model, setModel] = useState(DEFAULT_SETTINGS.defaultModel);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    conversations,
    activeConversation,
    isStreaming,
    error,
    sendMessage,
    newConversation,
    selectConversation,
    deleteConversation,
    stopStreaming,
  } = useChat({
    model,
    systemPrompt: DEFAULT_SETTINGS.defaultSystemPrompt,
  });

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const handleSend = useCallback(
    (content: string) => {
      sendMessage(content);
    },
    [sendMessage]
  );

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeId={activeConversation?.id ?? null}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={deleteConversation}
      />

      {/* Main Chat Area */}
      <div className={styles.main}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h4 className={styles.headerTitle}>OllyChat</h4>
            <span className={styles.headerSubtitle}>Enterprise O11y Assistant</span>
          </div>
          <ModelSelector value={model} onChange={setModel} />
        </div>

        {/* Error Banner */}
        {error && (
          <Alert title="Error" severity="error" className={styles.errorBanner}>
            {error}
          </Alert>
        )}

        {/* Messages */}
        <div className={styles.messages}>
          {!activeConversation && (
            <div className={styles.welcome}>
              <h2>Welcome to OllyChat</h2>
              <p>Ask questions about your infrastructure, investigate incidents, or explore metrics and logs.</p>
              <div className={styles.suggestions}>
                {[
                  'Show me the top 5 services by error rate in the last hour',
                  'Investigate high latency in the payment service',
                  'What deployments happened in the last 4 hours?',
                  'Generate a PromQL query for CPU usage by namespace',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    className={styles.suggestion}
                    onClick={() => handleSend(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeConversation?.messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          onStop={stopStreaming}
        />
      </div>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({
      display: 'flex',
      height: 'calc(100vh - 80px)',
      overflow: 'hidden',
    }),
    main: css({
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }),
    header: css({
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: theme.spacing(2),
      borderBottom: `1px solid ${theme.colors.border.weak}`,
      background: theme.colors.background.primary,
    }),
    headerLeft: css({
      display: 'flex',
      alignItems: 'baseline',
      gap: theme.spacing(1),
    }),
    headerTitle: css({
      margin: 0,
    }),
    headerSubtitle: css({
      color: theme.colors.text.secondary,
      fontSize: theme.typography.bodySmall.fontSize,
    }),
    errorBanner: css({
      margin: theme.spacing(1, 2),
    }),
    messages: css({
      flex: 1,
      overflow: 'auto',
      padding: theme.spacing(2),
    }),
    welcome: css({
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      textAlign: 'center',
      color: theme.colors.text.secondary,
      '& h2': {
        color: theme.colors.text.primary,
        marginBottom: theme.spacing(1),
      },
      '& p': {
        maxWidth: 500,
        marginBottom: theme.spacing(3),
      },
    }),
    suggestions: css({
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: theme.spacing(1),
      maxWidth: 600,
    }),
    suggestion: css({
      padding: theme.spacing(1.5, 2),
      background: theme.colors.background.secondary,
      border: `1px solid ${theme.colors.border.weak}`,
      borderRadius: theme.shape.radius.default,
      cursor: 'pointer',
      textAlign: 'left',
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.primary,
      transition: 'all 0.15s ease',
      '&:hover': {
        background: theme.colors.action.hover,
        borderColor: theme.colors.primary.border,
      },
    }),
  };
}
