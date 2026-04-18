import { useCallback, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { API, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE } from '../constants';
import { ChatMessage, Conversation, LLMEvent, TokenUsage } from '../types';

interface UseChatOptions {
  model: string;
  systemPrompt: string;
  maxTokens?: number;
  temperature?: number;
}

interface UseChatReturn {
  conversations: Conversation[];
  activeConversation: Conversation | null;
  isStreaming: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  newConversation: () => void;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  stopStreaming: () => void;
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;

  const updateConversation = useCallback((id: string, updater: (conv: Conversation) => Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? updater(c) : c)));
  }, []);

  const newConversation = useCallback(() => {
    const conv: Conversation = {
      id: uuidv4(),
      title: 'New Chat',
      messages: [],
      model: options.model,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }, [options.model]);

  const selectConversation = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) {
      setActiveId(null);
    }
  }, [activeId]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      let convId = activeId;

      // Auto-create conversation if none active
      if (!convId) {
        const conv: Conversation = {
          id: uuidv4(),
          title: content.slice(0, 50),
          messages: [],
          model: options.model,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        setConversations((prev) => [conv, ...prev]);
        convId = conv.id;
        setActiveId(convId);
      }

      // Add user message
      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content,
        timestamp: Date.now(),
      };

      // Add placeholder assistant message for streaming
      const assistantMsg: ChatMessage = {
        id: uuidv4(),
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        model: options.model,
        isStreaming: true,
      };

      const currentConvId = convId;
      updateConversation(currentConvId, (c) => ({
        ...c,
        messages: [...c.messages, userMsg, assistantMsg],
        title: c.messages.length === 0 ? content.slice(0, 50) : c.title,
        updatedAt: Date.now(),
      }));

      setIsStreaming(true);
      setError(null);

      const abortController = new AbortController();
      abortRef.current = abortController;

      try {
        // Build messages array for API
        const currentConv = conversations.find((c) => c.id === currentConvId);
        const historyMessages = (currentConv?.messages ?? []).map((m) => ({
          role: m.role,
          content: m.content,
        }));

        const response = await fetch(API.CHAT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: options.model,
            messages: [
              ...historyMessages,
              { role: 'user', content },
            ],
            system: options.systemPrompt,
            max_tokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
            temperature: options.temperature ?? DEFAULT_TEMPERATURE,
            stream: true,
          }),
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          const text = await response.text();
          throw new Error(`API error ${response.status}: ${text.slice(0, 200)}`);
        }

        // Parse SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let accumulatedContent = '';
        let usage: TokenUsage | undefined;
        let costUsd: number | undefined;

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });

          let sep: number;
          while ((sep = buffer.indexOf('\n\n')) !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);

            const dataLine = frame.split('\n').find((l) => l.startsWith('data: '));
            if (!dataLine) {
              continue;
            }
            const jsonStr = dataLine.slice(6);
            if (jsonStr === '[DONE]') {
              continue;
            }

            let event: LLMEvent;
            try {
              event = JSON.parse(jsonStr);
            } catch {
              continue;
            }

            switch (event.type) {
              case 'text':
                accumulatedContent += event.delta;
                updateConversation(currentConvId, (c) => ({
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsg.id ? { ...m, content: accumulatedContent } : m
                  ),
                }));
                break;

              case 'tool_start':
                // Tool calls rendered inline (Phase 2)
                accumulatedContent += `\n\n> **Tool:** \`${event.name}\`\n> Arguments: \`${JSON.stringify(event.input)}\`\n`;
                updateConversation(currentConvId, (c) => ({
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsg.id ? { ...m, content: accumulatedContent } : m
                  ),
                }));
                break;

              case 'tool_result':
                const resultPreview = event.error
                  ? `Error: ${event.error}`
                  : JSON.stringify(event.result).slice(0, 500);
                accumulatedContent += `> Result (${event.durationMs}ms): \`${resultPreview}\`\n\n`;
                updateConversation(currentConvId, (c) => ({
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsg.id ? { ...m, content: accumulatedContent } : m
                  ),
                }));
                break;

              case 'usage':
                usage = event.usage;
                costUsd = event.costUsd;
                break;

              case 'error':
                setError(event.message);
                break;

              case 'done':
                break;
            }
          }
        }

        // Finalize the assistant message
        updateConversation(currentConvId, (c) => ({
          ...c,
          messages: c.messages.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, content: accumulatedContent, isStreaming: false, usage, costUsd }
              : m
          ),
          updatedAt: Date.now(),
        }));
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          // User cancelled
          updateConversation(currentConvId, (c) => ({
            ...c,
            messages: c.messages.map((m) =>
              m.id === assistantMsg.id ? { ...m, isStreaming: false, content: m.content + '\n\n*[Cancelled]*' } : m
            ),
          }));
        } else {
          const errorMsg = err instanceof Error ? err.message : 'Unknown error';
          setError(errorMsg);
          updateConversation(currentConvId, (c) => ({
            ...c,
            messages: c.messages.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, isStreaming: false, content: `Error: ${errorMsg}` }
                : m
            ),
          }));
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [activeId, conversations, options, updateConversation]
  );

  return {
    conversations,
    activeConversation,
    isStreaming,
    error,
    sendMessage,
    newConversation,
    selectConversation,
    deleteConversation,
    stopStreaming,
  };
}
