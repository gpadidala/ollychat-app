"""OllyChat Orchestrator — FastAPI service combining LLM gateway, MCP client, and investigation engine."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import chat, models

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
