"""OllyChat Orchestrator configuration via environment variables."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # --- LLM Provider Keys ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    groq_api_key: str = ""

    # --- Ollama ---
    ollama_base_url: str = "http://ollama:11434"

    # --- Azure OpenAI ---
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-10-21"

    # --- Default LLM ---
    default_model: str = "claude-sonnet-4-6"
    default_max_tokens: int = 4096
    default_temperature: float = 0.2
    max_tool_loop_iterations: int = 8

    # --- Grafana Stack ---
    grafana_url: str = "http://grafana:3000"
    mimir_url: str = "http://mimir:9009"
    loki_url: str = "http://loki:3100"
    tempo_url: str = "http://tempo:3200"
    pyroscope_url: str = "http://pyroscope:4040"

    # --- MCP ---
    bifrost_url: str = "http://bifrost-core:8765"
    mcp_config_path: str = "./mcp/config.yaml"

    # --- OTEL ---
    otel_exporter_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "ollychat-orchestrator"

    # --- PII ---
    pii_enabled: bool = True
    pii_mode: str = "redact"  # log, redact, block, alert

    # --- Storage ---
    postgres_url: str = "postgresql://ollychat:ollychat@postgres:5432/ollychat"
    redis_url: str = "redis://redis:6379/0"

    model_config = {"env_prefix": "OLLYCHAT_", "env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
