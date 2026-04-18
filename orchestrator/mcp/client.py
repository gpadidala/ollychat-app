"""MCP Client Manager — manages connections to external MCP servers.

Adapted from o11y-sre-agent/agent/mcp/client.py with HTTP/SSE transport support
and Bifrost REST bridge integration.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
import structlog
import yaml
from pathlib import Path

logger = structlog.get_logger()

Transport = Literal["sse", "http", "stdio"]


@dataclass
class MCPServerConfig:
    name: str
    url: str
    transport: Transport = "sse"
    enabled: bool = True
    description: str = ""
    auth_method: str = "none"  # none, auth-header
    auth_token: str = ""
    tool_filter: list[str] = field(default_factory=list)


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    min_role: str = "viewer"


class MCPClientManager:
    """Manages connections to one or more MCP servers and their tool catalogs."""

    def __init__(self, config_path: str = "./mcp/config.yaml") -> None:
        self.servers: dict[str, MCPServerConfig] = {}
        self.tools: dict[str, ToolDef] = {}  # tool_name -> ToolDef
        self.status: dict[str, str] = {}
        self.config_path = Path(config_path)
        self._http_clients: dict[str, httpx.AsyncClient] = {}

    def load_config(self) -> None:
        if not self.config_path.exists():
            logger.info("mcp.config.not_found", path=str(self.config_path))
            return
        data = yaml.safe_load(self.config_path.read_text()) or {}
        for raw in data.get("servers", []):
            cfg = MCPServerConfig(
                name=raw["name"],
                url=raw["url"],
                transport=raw.get("transport", "sse"),
                enabled=raw.get("enabled", True),
                description=raw.get("description", ""),
                auth_method=raw.get("auth_method", "none"),
                auth_token=raw.get("auth_token", ""),
                tool_filter=raw.get("tool_filter", []),
            )
            # Expand ${VAR} in auth_token
            if cfg.auth_token.startswith("${") and cfg.auth_token.endswith("}"):
                cfg.auth_token = os.environ.get(cfg.auth_token[2:-1], "")
            self.servers[cfg.name] = cfg
        logger.info("mcp.config.loaded", count=len(self.servers))

    def save_config(self) -> None:
        data = {
            "servers": [
                {
                    "name": s.name, "url": s.url, "transport": s.transport,
                    "enabled": s.enabled, "description": s.description,
                    "auth_method": s.auth_method, "tool_filter": s.tool_filter,
                }
                for s in self.servers.values()
            ]
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(data, sort_keys=False))

    async def connect_all(self) -> None:
        tasks = [self._discover_tools(cfg) for cfg in self.servers.values() if cfg.enabled]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _discover_tools(self, cfg: MCPServerConfig) -> None:
        """Connect to server's REST bridge and discover available tools."""
        try:
            headers = {}
            if cfg.auth_method == "auth-header" and cfg.auth_token:
                headers["Authorization"] = f"Bearer {cfg.auth_token}"

            client = httpx.AsyncClient(timeout=30, headers=headers)
            self._http_clients[cfg.name] = client

            # Try Bifrost-style REST bridge first: /api/tools
            r = await client.get(f"{cfg.url}/api/tools")
            if r.status_code == 200:
                data = r.json()
                tool_list = data.get("data", data) if isinstance(data, dict) else data
                if isinstance(tool_list, list):
                    for t in tool_list:
                        name = t.get("name", "")
                        if cfg.tool_filter and name not in cfg.tool_filter:
                            continue
                        self.tools[f"{cfg.name}__{name}"] = ToolDef(
                            name=name,
                            description=t.get("description", ""),
                            input_schema=t.get("input_schema", t.get("inputSchema", {})),
                            server_name=cfg.name,
                            min_role=t.get("min_role", "viewer"),
                        )
                self.status[cfg.name] = "connected"
                logger.info("mcp.connected", server=cfg.name, tools=len([t for t in self.tools if t.startswith(cfg.name)]))
                return

            self.status[cfg.name] = f"error: HTTP {r.status_code}"
        except Exception as e:
            logger.error("mcp.connect.failed", server=cfg.name, error=str(e))
            self.status[cfg.name] = f"error: {e}"

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool via the server's REST bridge."""
        client = self._http_clients.get(server_name)
        if not client:
            raise RuntimeError(f"MCP server {server_name} not connected")

        cfg = self.servers.get(server_name)
        if not cfg:
            raise RuntimeError(f"MCP server {server_name} not configured")

        t0 = time.perf_counter()
        try:
            r = await client.post(
                f"{cfg.url}/api/tools/call",
                json={"name": tool_name, "arguments": arguments},
            )
            duration_ms = int((time.perf_counter() - t0) * 1000)

            if r.status_code != 200:
                return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:400]}", "duration_ms": duration_ms}

            data = r.json()
            if isinstance(data, dict) and "ok" in data:
                return {**data, "duration_ms": duration_ms}
            return {"ok": True, "data": data, "duration_ms": duration_ms}

        except Exception as e:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            return {"ok": False, "error": str(e), "duration_ms": duration_ms}

    def add_server(self, cfg: MCPServerConfig) -> None:
        self.servers[cfg.name] = cfg
        self.save_config()

    def remove_server(self, name: str) -> None:
        self.servers.pop(name, None)
        self.tools = {k: v for k, v in self.tools.items() if v.server_name != name}
        client = self._http_clients.pop(name, None)
        if client:
            asyncio.create_task(client.aclose())
        self.status.pop(name, None)
        self.save_config()

    def toggle(self, name: str, enabled: bool) -> None:
        if name in self.servers:
            self.servers[name].enabled = enabled
            self.save_config()

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": td.name,
                "description": td.description,
                "inputSchema": td.input_schema,
                "serverName": td.server_name,
                "minRole": td.min_role,
            }
            for td in self.tools.values()
        ]

    def list_servers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": cfg.name,
                "url": cfg.url,
                "transport": cfg.transport,
                "status": self.status.get(cfg.name, "disconnected"),
                "toolCount": len([t for t in self.tools.values() if t.server_name == cfg.name]),
                "authMethod": cfg.auth_method,
                "enabled": cfg.enabled,
            }
            for cfg in self.servers.values()
        ]

    async def close(self) -> None:
        for client in self._http_clients.values():
            await client.aclose()
        self._http_clients.clear()


# Singleton
_manager: MCPClientManager | None = None

def get_mcp_manager() -> MCPClientManager:
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager
