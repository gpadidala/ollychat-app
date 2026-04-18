"""Model catalog endpoint — lists available LLM models with pricing and capabilities."""
from __future__ import annotations

from fastapi import APIRouter

from config import get_settings

router = APIRouter()

# Model catalog — adapted from o11y-sre-agent/agent/llm/models.py
SUPPORTED_MODELS: dict[str, dict] = {
    # --- Anthropic ---
    "claude-opus-4-6": {
        "provider": "anthropic",
        "display_name": "Claude Opus 4.6",
        "context_window": 1_000_000,
        "cost_per_1k_in": 0.015,
        "cost_per_1k_out": 0.075,
        "supports_tools": True,
        "supports_streaming": True,
        "strengths": ["reasoning", "long_context", "coding", "investigation"],
    },
    "claude-sonnet-4-6": {
        "provider": "anthropic",
        "display_name": "Claude Sonnet 4.6",
        "context_window": 1_000_000,
        "cost_per_1k_in": 0.003,
        "cost_per_1k_out": 0.015,
        "supports_tools": True,
        "supports_streaming": True,
        "strengths": ["tools", "long_context", "balanced"],
    },
    "claude-haiku-4-5": {
        "provider": "anthropic",
        "display_name": "Claude Haiku 4.5",
        "context_window": 200_000,
        "cost_per_1k_in": 0.0008,
        "cost_per_1k_out": 0.004,
        "supports_tools": True,
        "supports_streaming": True,
        "strengths": ["speed", "cheap", "triage"],
    },
    # --- OpenAI ---
    "gpt-4o": {
        "provider": "openai",
        "display_name": "GPT-4o",
        "context_window": 128_000,
        "cost_per_1k_in": 0.0025,
        "cost_per_1k_out": 0.01,
        "supports_tools": True,
        "supports_streaming": True,
        "strengths": ["reasoning", "tools", "vision"],
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "display_name": "GPT-4o Mini",
        "context_window": 128_000,
        "cost_per_1k_in": 0.00015,
        "cost_per_1k_out": 0.0006,
        "supports_tools": True,
        "supports_streaming": True,
        "strengths": ["cheap", "speed", "triage"],
    },
    # --- Google ---
    "gemini-2.0-flash": {
        "provider": "google",
        "display_name": "Gemini 2.0 Flash",
        "context_window": 1_000_000,
        "cost_per_1k_in": 0.0001,
        "cost_per_1k_out": 0.0004,
        "supports_tools": False,
        "supports_streaming": True,
        "strengths": ["speed", "cheap", "long_context"],
    },
    # --- Ollama (local) ---
    "llama3.2:latest": {
        "provider": "ollama",
        "display_name": "Llama 3.2 (Local)",
        "context_window": 128_000,
        "cost_per_1k_in": 0.0,
        "cost_per_1k_out": 0.0,
        "supports_tools": False,
        "supports_streaming": True,
        "strengths": ["local", "private", "free"],
    },
}

# Which providers have API keys configured
def _available_providers() -> set[str]:
    settings = get_settings()
    providers = set()
    if settings.anthropic_api_key:
        providers.add("anthropic")
    if settings.openai_api_key:
        providers.add("openai")
    if settings.google_api_key:
        providers.add("google")
    if settings.groq_api_key:
        providers.add("groq")
    if settings.mistral_api_key:
        providers.add("mistral")
    # Ollama is always available (local)
    providers.add("ollama")
    return providers


@router.get("/models")
async def list_models():
    """List available LLM models filtered by configured API keys."""
    available = _available_providers()
    models = []
    for model_id, spec in SUPPORTED_MODELS.items():
        if spec["provider"] in available:
            models.append({
                "id": model_id,
                "provider": spec["provider"],
                "displayName": spec["display_name"],
                "contextWindow": spec["context_window"],
                "costPer1kIn": spec["cost_per_1k_in"],
                "costPer1kOut": spec["cost_per_1k_out"],
                "supportsTools": spec["supports_tools"],
                "supportsStreaming": spec["supports_streaming"],
                "strengths": spec["strengths"],
            })
    return {"models": models}
