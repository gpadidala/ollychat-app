# O11yBot Documentation

| Doc | Purpose |
|---|---|
| [USE_CASES.md](USE_CASES.md) | **Every use case O11yBot supports** — read/write/admin matrix + routing + RBAC |
| [ENTERPRISE.md](ENTERPRISE.md) | Production deployment, RBAC, self-observability, hardening checklist |
| [TESTING.md](TESTING.md) | **All 160+ tests** across 8 suites — every expected output documented |
| [VALIDATION.md](VALIDATION.md) | **20 end-to-end validation scenarios** — manual reproduction guide |
| [RBAC.md](RBAC.md) | Single MCP + multi-role tokens design + SA setup steps |
| [API_REFERENCE.md](API_REFERENCE.md) | All REST endpoints, SSE event types, MCP tools |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How to deploy to any Grafana instance |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams and data flow |

## Quick Links

### Services
- **Main Grafana**: http://localhost:3200 (admin/admin) — 113 dashboards
- **Orchestrator API**: http://localhost:8000
- **O11yBot MCP**: http://localhost:8765
- **Ollama LLM**: http://localhost:11434

### Run tests
```bash
cd tests
./preflight.sh              # service health check
./run-all-tests.sh          # full 147-test suite

# Individual suites:
./suite1-api.sh             # 17 tests — API
./suite2-intents.sh         # 19 tests — intent matcher
node suite3-widget.js       # 22 tests — SSE parser
node suite4-integration.js  # 18 tests — E2E integration
node suite5-negative.js     # 22 tests — errors + edge cases
node suite6-prompts.js      # 18 tests — prompt engineering
./suite7-categories.sh      # 31 tests — category intents
```

### Manual validation
See [VALIDATION.md](VALIDATION.md) for 20 step-by-step scenarios covering:
- Basic chat flow
- Category filters (AKS, Azure, OCI, etc.)
- Service-specific searches
- Window modes (normal/max/fullscreen)
- Per-user history isolation
- RBAC enforcement
- LLM fallback
- Incident analysis prompt
- Concurrent + stress
- Unicode handling

### Widget features
- Floating orange bubble, bottom-right corner (draggable)
- 4 window modes: FAB / Normal / Maximized / Fullscreen
- Keyboard: Enter to send, Esc to exit fullscreen
- Per-user chat history (keyed by Grafana login)
- Streaming markdown responses
- Intent + category-matched MCP tool calls
- Service-name auto-extraction

### Prompt engineering
5 query categories with tuned parameters:
| Category | Temperature | Max tokens |
|---|---|---|
| tool_result_formatting | 0.1 | 800 |
| observability_qa | 0.2 | 500 |
| promql_help | 0.15 | 600 |
| incident_analysis | 0.3 | 1500 |
| chitchat | 0.5 | 150 |

### Categories supported (35+)
- **Cloud**: AKS, Azure, OCI, GCP, GKE, AWS
- **Kubernetes**: kubernetes, containers
- **Databases**: postgres, mysql, redis, cassandra, cosmos
- **Observability**: loki, mimir, tempo, pyroscope, lgtm
- **Compliance**: PCI, HIPAA, GDPR, SOC2, security
- **SRE**: SLO, RED metrics, performance, errors
- **Layers**: L0-L3 (exec/domain/service/deep-dive)
- **Services**: auto-extracts `*-service`, `*-svc`, `*-api`, `*-gateway`
