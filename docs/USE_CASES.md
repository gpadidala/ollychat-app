# O11yBot — Use Case Matrix

Every row below is a real intent match — no fabricated answers. When a user asks something
that matches, the orchestrator routes to the listed MCP tool (or static authoring help), applies
RBAC, streams the result back, and (for fuzzy paths) reranks via LLM-as-judge.

## Read operations (role: viewer+)

| Use case | Example prompt | MCP tool |
|---|---|---|
| List every dashboard | `list all dashboards` | `list_dashboards` |
| Filter by category | `list AKS dashboards` · `Azure dashboards` · `Loki` | `list_dashboards(tags=…)` |
| Search by title | `search dashboards postgres` | `search_dashboards` |
| Service-specific search | `payment-service dashboards` | `search_dashboards(query=svc)` |
| Multi-keyword fuzzy | `oracle kpi dashbords` (typo-tolerant) | `list_dashboards` + local fuzzy + judge |
| Dashboard detail by UID | `show dashboard abc123XYZ` · `describe dashboard abc123XYZ` | `get_dashboard` |
| Panel inventory | `panels in abc123XYZ` · `what panels in abc123XYZ` | `get_dashboard_panels` |
| List alert rules | `list all alert rules` | `list_alert_rules` |
| Firing instances | `show firing alerts` · `active alerts` | `list_alert_instances` |
| Explain an alert | `explain alert abc123XYZ` · `why is abc123XYZ firing?` | `get_alert_rule` |
| List datasources | `list datasources` | `list_datasources` |
| Datasource detail | `get datasource prometheus` | `get_datasource` |
| Run a PromQL query | `run promql sum(rate(http_requests_total[5m]))` | `query_datasource` |
| List folders | `list folders` | `list_folders` |
| Grafana health | `check grafana health` · `ping` | `health_check` |
| MCP / server info | `mcp server info` · `grafana info` | `get_server_info` |

## Write operations (role: editor+)

| Use case | Example prompt | MCP tool |
|---|---|---|
| Create a dashboard | `create a dashboard called "Payment SLOs"` | `create_dashboard` |
| Create service dashboard | `create dashboard for checkout-service` | `create_dashboard(title, tags=[svc])` |
| Create folder | `create folder "Platform team"` | `create_folder` |
| Silence an alert | `silence alert abc123XYZ` | `silence_alert` |

## Admin operations (role: admin)

| Use case | Example prompt | MCP tool |
|---|---|---|
| List users | `list users` | `list_users` |
| List service accounts | `list service accounts` | `list_service_accounts` |
| Delete a dashboard | `delete dashboard abc123XYZ` | `delete_dashboard` |

## Authoring help (static — no tool call)

| Use case | Example prompt | Response |
|---|---|---|
| PromQL cookbook | `promql cookbook` · `promql examples` | Copy-paste-ready PromQL patterns |
| LogQL cookbook | `logql examples` | Labels, JSON parsing, regex extraction |
| TraceQL cookbook | `traceql templates` | Duration filters, service chaining |
| SLO authoring | `slo cheat sheet` | SLI/SLO/burn-rate recipe |

## Navigation & diagnostics

| Use case | Example prompt | Response |
|---|---|---|
| Where to find a feature | `where do I find alert rules?` | Grafana UI map |
| Decode an error | `decode error: context deadline exceeded` | Common causes + fixes |

## How the orchestrator routes a query

```
user message
   │
   ▼
[Phase 0]  "search dashboards …"   → search_dashboards      (exact)
[Phase 1]  "xyz-service dashboards" → search_dashboards     (fuzzy + judge)
[Phase 2]  "list AKS dashboards"   → list_dashboards(tags)  (single category)
[Phase 3]  exact patterns (list datasources, show firing alerts, etc.)
[Phase 4]  "oracle" (≤ 1 keyword)  → list_dashboards(tags)  (category-only)
[Phase 5]  "random multi-word"     → list_dashboards()      (local fuzzy + judge)
   │
   ▼
no match → classify → LLM answer (PromQL explainer, incident analysis, chit-chat)
```

Multi-keyword queries skip Phase 2/4 so every keyword must intersect in the local fuzzy score —
that's why `oracle kpi dashbords` returns only KPI-on-OCI dashboards, not all 20 OCI ones.

## LLM-as-judge reranker

Fuzzy paths (Phase 1 + Phase 5) send the top 20 candidates through a low-temperature (0.1)
judge prompt that returns JSON:

```json
[{"uid": "…", "reason": "…", "score": 0-100}]
```

The widget then renders:

```
🎯 Top N dashboards for <query>:
- Title · Folder · score 93
  💡 short reason
  [Open dashboard](/d/…)
```

If the judge errors or returns junk, the original deterministic formatter output is used —
never a regression.

## RBAC

| Role | Can do | Cannot do |
|---|---|---|
| `viewer` | all read ops, PromQL help, navigation | any mutation, user listing |
| `editor` | + `silence_alert`, `create_dashboard`, `update_dashboard`, `create_folder` | delete dashboards, list users |
| `admin` | everything above + `delete_dashboard`, `list_users`, `list_service_accounts` | — |

Role comes from the Grafana session (`X-Grafana-Role` header), forwarded by the widget,
validated by the orchestrator, enforced at the MCP layer before the tool runs.
