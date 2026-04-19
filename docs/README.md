# O11yBot Documentation

**Start here** if you're new — the guides are ordered by typical journey:

| Step | Doc | When to read it |
|---|---|---|
| 0 | [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Get oriented — folder tree + per-file purpose |
| 1 | [INSTALLATION.md](INSTALLATION.md) | Zero → boot. OSS + Enterprise paths, SA tokens, env vars, first smoke test |
| 2 | [DEPLOYMENT.md](DEPLOYMENT.md) | Production paths — Docker Compose, Kubernetes/Helm, bare-metal systemd — each with validation + rollback |
| 3 | [VALIDATION.md](VALIDATION.md) | 9-command post-deploy smoke test + 20 end-to-end scenarios |
| 4 | [USE_CASES.md](USE_CASES.md) | Full 53-tool capability matrix by role + example prompts |
| 5 | [ENTERPRISE.md](ENTERPRISE.md) | RBAC, self-observability, hardening, scaling |
| 6 | [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams + data flow |
| 7 | [API_REFERENCE.md](API_REFERENCE.md) | REST endpoints + SSE event types + MCP tool catalog |
| 8 | [RBAC.md](RBAC.md) | Role design + service-account setup |
| 9 | [TESTING.md](TESTING.md) | All 160 automated tests, expected outputs |

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
