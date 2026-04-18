/** Core types for OllyChat Grafana App Plugin */

// --- Chat Types ---

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  model?: string;
  toolCalls?: ToolCall[];
  usage?: TokenUsage;
  costUsd?: number;
  piiDetected?: PIIDetection[];
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  model: string;
  createdAt: number;
  updatedAt: number;
}

// --- Streaming Events (from orchestrator SSE) ---

export type LLMEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool_start'; id: string; name: string; input: Record<string, unknown> }
  | { type: 'tool_result'; id: string; result: unknown; error?: string; durationMs: number }
  | { type: 'usage'; usage: TokenUsage; costUsd: number }
  | { type: 'done' }
  | { type: 'error'; message: string };

// --- Tool Types ---

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: 'pending' | 'approved' | 'rejected' | 'running' | 'complete' | 'error';
  result?: unknown;
  error?: string;
  durationMs?: number;
}

export interface MCPToolDef {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  serverName: string;
  minRole?: 'viewer' | 'editor' | 'admin';
}

export interface MCPServer {
  name: string;
  url: string;
  transport: 'sse' | 'http' | 'stdio';
  status: 'connected' | 'disconnected' | 'error';
  toolCount: number;
  authMethod: 'oauth' | 'auth-header' | 'none';
  enabled: boolean;
}

// --- Token & Cost Types ---

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

// --- PII Types ---

export interface PIIDetection {
  type: string;
  start: number;
  end: number;
  confidence: number;
  action: 'log' | 'redact' | 'block' | 'alert';
}

// --- Model Types ---

export interface ModelInfo {
  id: string;
  provider: string;
  displayName: string;
  contextWindow: number;
  costPer1kIn: number;
  costPer1kOut: number;
  supportsTools: boolean;
  supportsStreaming: boolean;
  strengths: string[];
}

// --- Investigation Types ---

export interface Investigation {
  id: string;
  question: string;
  status: 'running' | 'complete' | 'failed';
  trigger: 'manual' | 'irm-alert' | 'irm-incident';
  rootCause?: string;
  confidence: number;
  impact?: string;
  affectedServices: string[];
  recommendedActions: string[];
  observations: Observation[];
  hypotheses: Hypothesis[];
  report?: string;
  createdAt: number;
  completedAt?: number;
  costUsd: number;
}

export interface Observation {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  ok: boolean;
  error?: string;
  timestamp: number;
}

export interface Hypothesis {
  rank: number;
  pattern: string;
  confidence: number;
  evidence: string[];
  impact: string;
  remediation?: string;
  rollback?: string;
}

// --- Skills & Rules Types ---

export interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  systemPrompt: string;
  toolWhitelist: string[];
  modelPreference?: string;
  slashCommand?: string;
  tags: string[];
  visibility: 'just-me' | 'everybody';
  createdBy: string;
  createdAt: number;
  updatedAt: number;
}

export interface Rule {
  id: string;
  name: string;
  content: string;
  scope: 'just-me' | 'everybody';
  enabled: boolean;
  applications: string[];
}

// --- Plugin Settings ---

export interface OllyChatSettings {
  orchestratorUrl: string;
  defaultModel: string;
  defaultSystemPrompt: string;
  enablePII: boolean;
  piiMode: 'log' | 'redact' | 'block' | 'alert';
  enableCostTracking: boolean;
  maxToolLoopIterations: number;
}

export const DEFAULT_SETTINGS: OllyChatSettings = {
  orchestratorUrl: 'http://localhost:8000',
  defaultModel: 'claude-sonnet-4-6',
  defaultSystemPrompt: `You are OllyChat, an AI assistant specialized in observability, infrastructure, and incident response. You have access to Grafana dashboards, Prometheus metrics, Loki logs, and Tempo traces through MCP tools.

When investigating issues:
1. Start with golden signals (latency, traffic, errors, saturation)
2. Correlate across metrics, logs, and traces
3. Check recent deployments before assuming code issues
4. Provide specific queries (PromQL, LogQL, TraceQL) with your findings
5. Be concise and actionable`,
  enablePII: true,
  piiMode: 'redact',
  enableCostTracking: true,
  maxToolLoopIterations: 8,
};
