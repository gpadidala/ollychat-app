"""Category dictionary — maps natural language keywords to Grafana tags/folders.

Used by the intent matcher to filter `list_dashboards`, `list_alert_rules`, etc.
by category without requiring the user to know exact tag names.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────
# Category → [tag patterns] mapping
# ─────────────────────────────────────────────────────────────
# Keys: canonical category names (lowercase)
# Values: list of Grafana tags to filter by (OR semantics)
CATEGORIES: dict[str, dict] = {
    # ═════ CLOUD PROVIDERS ═════
    "aks": {
        "label": "AKS (Azure Kubernetes Service)",
        "tags": ["aks", "kubernetes"],
        "folder_hints": ["Azure"],
        "keywords": ["aks", "azure kubernetes", "azure k8s"],
    },
    "azure": {
        "label": "Azure Cloud",
        "tags": ["azure"],
        "folder_hints": ["Azure — Cloud Infrastructure"],
        "keywords": ["azure", "az ", "azure cloud"],
    },
    "gcp": {
        "label": "Google Cloud Platform",
        "tags": ["gcp", "google", "google-cloud"],
        "folder_hints": ["GCP"],
        "keywords": ["gcp", "google cloud", "gke", "google kubernetes"],
    },
    "gke": {
        "label": "GKE (Google Kubernetes Engine)",
        "tags": ["gke", "kubernetes"],
        "folder_hints": ["GCP"],
        "keywords": ["gke", "google kubernetes"],
    },
    "oci": {
        "label": "Oracle Cloud Infrastructure",
        "tags": ["oci"],
        "folder_hints": ["OCI — Oracle Cloud Infrastructure"],
        "keywords": ["oci", "oracle cloud", "oracle"],
    },
    "aws": {
        "label": "AWS (Amazon Web Services)",
        "tags": ["aws", "eks"],
        "folder_hints": ["AWS"],
        "keywords": ["aws", "amazon", "eks"],
    },

    # ═════ KUBERNETES ═════
    "kubernetes": {
        "label": "Kubernetes",
        "tags": ["kubernetes", "k8s"],
        "folder_hints": [],
        "keywords": ["kubernetes", "k8s", "kubectl", "pods", "nodes", "cluster"],
    },
    "containers": {
        "label": "Container Workloads",
        "tags": ["container", "docker", "pod"],
        "folder_hints": [],
        "keywords": ["container", "docker", "pods", "workload"],
    },

    # ═════ DATA STORES ═════
    "database": {
        "label": "Database",
        "tags": ["database", "db", "sql"],
        "folder_hints": [],
        "keywords": ["database", "db-level", "sql database"],
    },
    "postgresql": {
        "label": "PostgreSQL",
        "tags": ["postgresql", "postgres", "pg"],
        "folder_hints": [],
        "keywords": ["postgres", "postgresql", "pg"],
    },
    "mysql": {
        "label": "MySQL",
        "tags": ["mysql"],
        "folder_hints": [],
        "keywords": ["mysql", "mariadb"],
    },
    "redis": {
        "label": "Redis",
        "tags": ["redis", "cache"],
        "folder_hints": [],
        "keywords": ["redis", "cache"],
    },
    "cassandra": {
        "label": "Cassandra",
        "tags": ["cassandra"],
        "folder_hints": [],
        "keywords": ["cassandra"],
    },
    "cosmos": {
        "label": "Azure Cosmos DB",
        "tags": ["cosmos", "cosmosdb", "nosql"],
        "folder_hints": [],
        "keywords": ["cosmos", "cosmosdb"],
    },

    # ═════ OBSERVABILITY SIGNALS ═════
    "loki": {
        "label": "Loki (logs)",
        "tags": ["loki", "logs"],
        "folder_hints": ["Loki"],
        "keywords": ["loki", "log ", "logs"],
    },
    "mimir": {
        "label": "Mimir (metrics)",
        "tags": ["mimir", "prometheus", "metrics"],
        "folder_hints": ["Mimir"],
        "keywords": ["mimir", "prometheus", "metrics dashboard"],
    },
    "tempo": {
        "label": "Tempo (traces)",
        "tags": ["tempo", "traces", "tracing"],
        "folder_hints": ["Tempo"],
        "keywords": ["tempo", "trace", "tracing", "distributed tracing"],
    },
    "pyroscope": {
        "label": "Pyroscope (profiles)",
        "tags": ["pyroscope", "profiling", "flamegraph"],
        "folder_hints": ["Pyroscope"],
        "keywords": ["pyroscope", "profile", "profiling", "flamegraph", "cpu profile"],
    },
    "lgtm": {
        "label": "LGTM Stack (Loki/Grafana/Tempo/Mimir)",
        "tags": ["lgtm"],
        "folder_hints": [],
        "keywords": ["lgtm", "lgtm stack"],
    },

    # ═════ COMPLIANCE & SECURITY ═════
    "pci": {
        "label": "PCI DSS Compliance",
        "tags": ["pci", "pci-dss", "compliance"],
        "folder_hints": ["Compliance", "Security"],
        "keywords": ["pci", "pci-dss", "pci dss", "payment card"],
    },
    "hipaa": {
        "label": "HIPAA / PHI",
        "tags": ["hipaa", "phi", "compliance"],
        "folder_hints": ["Compliance", "Security"],
        "keywords": ["hipaa", "phi", "protected health"],
    },
    "gdpr": {
        "label": "GDPR",
        "tags": ["gdpr", "privacy", "compliance"],
        "folder_hints": [],
        "keywords": ["gdpr", "privacy"],
    },
    "soc2": {
        "label": "SOC 2",
        "tags": ["soc2", "soc-2", "compliance"],
        "folder_hints": [],
        "keywords": ["soc 2", "soc2", "soc-2"],
    },
    "security": {
        "label": "Security",
        "tags": ["security", "audit", "vulnerability"],
        "folder_hints": ["Security"],
        "keywords": ["security", "audit", "vuln", "compliance", "access control"],
    },

    # ═════ SRE / OBSERVABILITY PATTERNS ═════
    "slo": {
        "label": "SLO / SLI / Error Budget",
        "tags": ["slo", "sli", "error-budget"],
        "folder_hints": [],
        "keywords": ["slo", "sli", "error budget", "service level"],
    },
    "red_metrics": {
        "label": "RED Metrics (Rate / Errors / Duration)",
        "tags": ["red-metrics", "red", "golden-signals"],
        "folder_hints": [],
        "keywords": ["red method", "red metrics", "red dashboard", "red analysis",
                     "golden signals", "four signals", "rate errors duration"],
    },
    "performance": {
        "label": "Performance",
        "tags": ["performance", "latency", "throughput"],
        "folder_hints": [],
        "keywords": ["performance", "latency", "throughput", "qps", "rps"],
    },
    "errors": {
        "label": "Errors (4xx / 5xx)",
        "tags": ["errors", "4xx", "5xx", "error-rate"],
        "folder_hints": [],
        "keywords": ["error", "errors", "error rate", "4xx", "5xx", "http errors", "5xx errors"],
    },

    # ═════ APPLICATION LAYERS ═════
    "application": {
        "label": "Application Level",
        "tags": ["application", "application-level", "apm"],
        "folder_hints": [],
        "keywords": ["application", "app level", "apm", "application insights"],
    },
    "appservice": {
        "label": "Azure App Service",
        "tags": ["appservice", "webapp"],
        "folder_hints": [],
        "keywords": ["app service", "appservice", "web app"],
    },
    "network": {
        "label": "Network",
        "tags": ["network", "networking", "dns"],
        "folder_hints": [],
        "keywords": ["network", "networking", "dns", "connectivity"],
    },
    "storage": {
        "label": "Storage / Persistent Volumes",
        "tags": ["storage", "pv", "pvc", "volume"],
        "folder_hints": [],
        "keywords": ["storage", "volume", "pv", "pvc", "disk"],
    },

    # ═════ BUSINESS / PLATFORM ═════
    "executive": {
        "label": "Executive / Leadership",
        "tags": ["executive", "c-suite", "leadership"],
        "folder_hints": ["Platform & Executive", "L0 — Executive"],
        # note: avoid "board" — it matches "dashboards"
        "keywords": ["executive", "c-suite", "leadership", "exec team"],
    },
    "capacity": {
        "label": "Capacity Planning",
        "tags": ["capacity", "planning", "forecasting"],
        "folder_hints": [],
        "keywords": ["capacity", "planning", "forecast"],
    },
    "cost": {
        "label": "Cost / FinOps",
        "tags": ["cost", "finops", "billing"],
        "folder_hints": [],
        "keywords": ["cost", "finops", "billing", "spend"],
    },

    # ═════ LEVELS (L0-L3) ═════
    "l0": {
        "label": "L0 — Executive Command Center",
        "tags": ["l0", "executive"],
        "folder_hints": ["L0 — Executive"],
        "keywords": ["l0", "level 0", "command center"],
    },
    "l1": {
        "label": "L1 — Domain Overview",
        "tags": ["l1", "overview"],
        "folder_hints": ["L1 — Domain"],
        "keywords": ["l1", "level 1", "domain overview"],
    },
    "l2": {
        "label": "L2 — Service Golden Signals",
        "tags": ["l2", "golden-signals"],
        "folder_hints": ["L2 — Service"],
        "keywords": ["l2", "level 2", "service signals"],
    },
    "l3": {
        "label": "L3 — Deep Dive & Debug",
        "tags": ["l3", "deep-dive"],
        "folder_hints": ["L3 — Deep Dive"],
        "keywords": ["l3", "level 3", "deep dive", "debug"],
    },

    # ═════ PLUGINS / INTEGRATIONS ═════
    "plugins": {
        "label": "Plugins",
        "tags": ["plugin", "integration"],
        "folder_hints": [],
        "keywords": ["plugin", "plugins", "integration"],
    },
}


def find_category(text: str) -> dict | None:
    """Match a category by checking keywords in the text.

    Returns the category dict (with label, tags, keywords) or None if no match.
    Priority: longer keywords win (most specific match).
    """
    if not text:
        return None
    text_lower = text.lower()
    # Sort keywords by length descending to prefer specific matches
    best_match = None
    best_len = 0
    for cat_key, cat in CATEGORIES.items():
        for kw in cat["keywords"]:
            if kw in text_lower and len(kw) > best_len:
                best_match = {"key": cat_key, **cat}
                best_len = len(kw)
    return best_match


def extract_service_name(text: str) -> str | None:
    """Extract a service name from user query.

    Looks for patterns like:
      - "payment-service"
      - "api-gateway"
      - "user service"
      - "for X"
    """
    if not text:
        return None
    import re
    # Pattern 1: explicit service-name-service
    m = re.search(r"\b([a-z][a-z0-9-]+(?:-service|-svc|-api|-gateway))\b", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Pattern 2: "for <service>" or "about <service>"
    m = re.search(r"(?:for|about|of|on)\s+([a-z][a-z0-9-]{2,30})\b", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).lower()
        # Filter out common words
        if candidate not in {"the", "all", "any", "this", "that", "grafana", "service"}:
            return candidate
    return None
