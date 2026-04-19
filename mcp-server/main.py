"""O11yBot MCP server — REST bridge for the orchestrator.

Exposes /api/tools and /api/tools/call compatible with the orchestrator's
existing MCP client, so the orchestrator is point-and-shoot — change one URL.
"""
from __future__ import annotations

import inspect

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from grafana_client import close_all
from rbac import enforce, normalize_role
from registry import get_tool, list_tools, tool_count

# Importing this package triggers @tool registration for every tool file.
import tools  # noqa: F401

logger = structlog.get_logger()

app = FastAPI(title="O11yBot MCP Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    s = get_settings()
    logger.info(
        "o11ybot-mcp.startup",
        grafana_url=s.grafana_url,
        tools=tool_count(),
        viewer_token_set=bool(s.viewer_token),
        editor_token_set=bool(s.editor_token),
        admin_token_set=bool(s.admin_token),
    )


@app.on_event("shutdown")
async def _shutdown() -> None:
    await close_all()


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    return {"ok": True, "grafana_url": s.grafana_url, "tools": tool_count()}


@app.get("/api/tools")
async def api_list_tools() -> JSONResponse:
    return JSONResponse({"ok": True, "data": list_tools()})


@app.post("/api/tools/call")
async def api_call_tool(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": "ValueError", "message": f"invalid JSON: {e}"}, status_code=400)

    name = (body or {}).get("name")
    args = (body or {}).get("arguments") or {}
    if not isinstance(name, str) or not name:
        return JSONResponse({"ok": False, "error": "ValueError", "message": "body.name required"}, status_code=400)
    if not isinstance(args, dict):
        return JSONResponse({"ok": False, "error": "ValueError", "message": "body.arguments must be object"}, status_code=400)

    role = normalize_role(args.pop("role", None))

    tool_def = get_tool(name)
    if tool_def is None:
        return JSONResponse(
            {"ok": False, "error": "UnknownTool", "message": f"no such tool: {name}"},
            status_code=404,
        )

    try:
        enforce(name, role)
    except PermissionError as e:
        return JSONResponse({"ok": False, "error": "PermissionError", "message": str(e)}, status_code=403)

    # Filter args to those the function accepts
    sig = inspect.signature(tool_def.fn)
    accepted = set(sig.parameters.keys())
    call_args = {k: v for k, v in args.items() if k in accepted}
    if "role" in accepted:
        call_args["role"] = role

    try:
        result = await tool_def.fn(**call_args)
    except PermissionError as e:
        return JSONResponse({"ok": False, "error": "PermissionError", "message": str(e)}, status_code=403)
    except Exception as e:  # noqa: BLE001
        logger.error("tool.failed", tool=name, error=str(e))
        return JSONResponse(
            {"ok": False, "error": e.__class__.__name__, "message": str(e)},
            status_code=500,
        )

    return JSONResponse({"ok": True, "data": result})
