/** OllyChat constants and configuration */

export const PLUGIN_ID = 'gopal-ollychat-app';
export const PLUGIN_BASE_URL = `/api/plugins/${PLUGIN_ID}/resources`;

// API paths (proxied through Go backend to Python orchestrator)
export const API = {
  CHAT: `${PLUGIN_BASE_URL}/api/v1/chat`,
  MODELS: `${PLUGIN_BASE_URL}/api/v1/models`,
  HEALTH: `${PLUGIN_BASE_URL}/api/v1/health`,
  MCP_SERVERS: `${PLUGIN_BASE_URL}/api/v1/mcp/servers`,
  MCP_TOOLS: `${PLUGIN_BASE_URL}/api/v1/mcp/tools`,
  MCP_TOOL_CALL: `${PLUGIN_BASE_URL}/api/v1/mcp/tools/call`,
  INVESTIGATE: `${PLUGIN_BASE_URL}/api/v1/investigate`,
  SKILLS: `${PLUGIN_BASE_URL}/api/v1/skills`,
  RULES: `${PLUGIN_BASE_URL}/api/v1/rules`,
} as const;

export const MAX_MESSAGE_LENGTH = 32_000;
export const MAX_TOOL_RESULT_LENGTH = 20_000;
export const DEFAULT_MAX_TOKENS = 4096;
export const DEFAULT_TEMPERATURE = 0.2;
