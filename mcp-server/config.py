"""Settings loaded from env vars — deploy anywhere by pointing at any Grafana."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """O11yBot MCP server settings.

    All driven by env vars so the plugin + MCP stack can be dropped into
    any Grafana instance without code changes.
    """

    grafana_url: str = field(
        default_factory=lambda: os.environ.get("GRAFANA_URL", "http://host.docker.internal:3200").rstrip("/")
    )

    # Role-based tokens. If only GRAFANA_TOKEN is set, that single token is
    # used for every role — useful for quick single-tenant demos. For real
    # RBAC, set the three separately.
    viewer_token: str = field(
        default_factory=lambda: os.environ.get("GRAFANA_VIEWER_TOKEN")
        or os.environ.get("GRAFANA_TOKEN", "")
    )
    editor_token: str = field(
        default_factory=lambda: os.environ.get("GRAFANA_EDITOR_TOKEN")
        or os.environ.get("GRAFANA_TOKEN", "")
    )
    admin_token: str = field(
        default_factory=lambda: os.environ.get("GRAFANA_ADMIN_TOKEN")
        or os.environ.get("GRAFANA_TOKEN", "")
    )

    port: int = field(
        default_factory=lambda: int(os.environ.get("MCP_SERVER_PORT", "8765"))
    )
    tls_verify: bool = field(
        default_factory=lambda: os.environ.get("GRAFANA_TLS_VERIFY", "true").lower() != "false"
    )
    request_timeout_s: float = field(
        default_factory=lambda: float(os.environ.get("GRAFANA_TIMEOUT_S", "30"))
    )

    def token_for_role(self, role: str) -> str:
        role = (role or "viewer").lower()
        if role == "admin":
            return self.admin_token
        if role == "editor":
            return self.editor_token
        return self.viewer_token


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
