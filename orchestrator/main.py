"""OllyChat Orchestrator — FastAPI service combining LLM gateway, MCP client, and investigation engine."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import chat, models, mcp, investigate, skills, rules
from guardrails.router import router as guardrails_router

# --- Structured Logging ---
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    settings = get_settings()
    logger.info(
        "OllyChat Orchestrator starting",
        default_model=settings.default_model,
        pii_enabled=settings.pii_enabled,
        pii_mode=settings.pii_mode,
    )

    # Initialize OTEL (optional — gracefully skip if collector unavailable)
    try:
        from otel_setup import init_otel
        init_otel(settings)
        logger.info("OpenTelemetry initialized", endpoint=settings.otel_exporter_endpoint)
    except Exception as e:
        logger.warning("OpenTelemetry initialization failed, continuing without telemetry", error=str(e))

    # Auto-register the bundled O11yBot MCP server so a fresh `docker
    # compose up` has a connected MCP without any manual curl step. The
    # server URL is read from OLLYCHAT_BIFROST_URL (compose sets it to the
    # internal service name `http://ollychat-mcp:8765`).
    try:
        from mcp.client import MCPServerConfig, get_mcp_manager
        mgr = get_mcp_manager()
        mgr.load_config()
        if "bifrost-grafana" not in mgr.servers:
            mgr.servers["bifrost-grafana"] = MCPServerConfig(
                name="bifrost-grafana",
                url=settings.bifrost_url.rstrip("/"),
                transport="sse",
                enabled=True,
            )
        await mgr.connect_all()
        status = mgr.status.get("bifrost-grafana", "unknown")
        tools = len([t for t in mgr.tools.values() if t.server_name == "bifrost-grafana"])
        logger.info("mcp.auto-registered", status=status, tools=tools, url=settings.bifrost_url)
    except Exception as e:
        logger.warning("mcp.auto-register.failed — continuing without MCP",
                       error=str(e))

    yield

    logger.info("OllyChat Orchestrator shutting down")


# --- FastAPI App ---
app = FastAPI(
    title="OllyChat Orchestrator",
    description="LLM Gateway + MCP Client + Investigation Engine for OllyChat Grafana Plugin",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(models.router, prefix="/api/v1", tags=["models"])
app.include_router(mcp.router, prefix="/api/v1", tags=["mcp"])
app.include_router(investigate.router, prefix="/api/v1", tags=["investigate"])
app.include_router(skills.router, prefix="/api/v1", tags=["skills"])
app.include_router(rules.router, prefix="/api/v1", tags=["rules"])
app.include_router(guardrails_router, prefix="/api/v1", tags=["guardrails"])

# --- v2 Interactive Reasoning Canvas (feature-flagged) ---
# Gated behind OLLYBOT_INTERACTIVE_MODE. v1 surfaces above are untouched.
from v2 import interactive_mode_enabled
if interactive_mode_enabled():
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    from v2 import stream as v2_stream

    app.include_router(v2_stream.router, prefix="/api", tags=["v2"])

    _STATIC = Path(__file__).parent / "static"
    if _STATIC.exists():
        app.mount("/api/v2/static", StaticFiles(directory=str(_STATIC)), name="v2-static")

        @app.get("/api/v2/canvas", tags=["v2"])
        async def v2_canvas_page() -> FileResponse:
            """Minimal HTML demo canvas (ADR-0002). Debug / QA surface."""
            return FileResponse(str(_STATIC / "canvas.html"))

    logger.info("v2.interactive_mode.enabled",
                endpoints=["/api/v2/stream (WS)", "/api/v2/canvas"])
else:
    logger.info("v2.interactive_mode.disabled",
                hint="Set OLLYBOT_INTERACTIVE_MODE=true to enable /api/v2/*")


@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ollychat-orchestrator",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    s = get_settings()
    uvicorn.run("main:app", host=s.host, port=s.port, log_level=s.log_level, reload=True)
