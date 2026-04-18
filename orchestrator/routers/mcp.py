"""MCP server management and tool call endpoints."""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from mcp.client import MCPClientManager, MCPServerConfig, get_mcp_manager

logger = structlog.get_logger()
router = APIRouter()


class AddServerRequest(BaseModel):
    name: str
    url: str
    transport: str = "sse"
    auth_method: str = "none"
    auth_token: str = ""
    tool_filter: list[str] = []


class ToggleRequest(BaseModel):
    enabled: bool


class ToolCallRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = {}


@router.get("/mcp/servers")
async def list_servers():
    mgr = get_mcp_manager()
    return {"servers": mgr.list_servers()}


@router.post("/mcp/servers")
async def add_server(body: AddServerRequest):
    mgr = get_mcp_manager()
    cfg = MCPServerConfig(
        name=body.name,
        url=body.url,
        transport=body.transport,
        auth_method=body.auth_method,
        auth_token=body.auth_token,
        tool_filter=body.tool_filter,
    )
    mgr.add_server(cfg)
    await mgr._discover_tools(cfg)
    logger.info("mcp.server.added", name=body.name, url=body.url)
    return {"ok": True, "server": mgr.list_servers()[-1]}


@router.delete("/mcp/servers/{name}")
async def remove_server(name: str):
    mgr = get_mcp_manager()
    mgr.remove_server(name)
    logger.info("mcp.server.removed", name=name)
    return {"ok": True}


@router.post("/mcp/servers/{name}/toggle")
async def toggle_server(name: str, body: ToggleRequest):
    mgr = get_mcp_manager()
    mgr.toggle(name, body.enabled)
    return {"ok": True}


@router.get("/mcp/tools")
async def list_tools():
    mgr = get_mcp_manager()
    return {"tools": mgr.list_tools()}


@router.post("/mcp/tools/call")
async def call_tool(body: ToolCallRequest):
    mgr = get_mcp_manager()
    try:
        result = await mgr.call_tool(body.server_name, body.tool_name, body.arguments)
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "duration_ms": 0}
    except Exception as e:
        logger.error("mcp.tool.call.exception", error=str(e))
        return {"ok": False, "error": f"Internal error: {e}", "duration_ms": 0}
    logger.info(
        "mcp.tool.called",
        server=body.server_name,
        tool=body.tool_name,
        ok=result.get("ok"),
        duration_ms=result.get("duration_ms"),
    )
    return result
