# O11yBot — Enterprise Use Case Matrix

Every row is a real intent match that lands on a real MCP tool. Nothing is
fabricated. RBAC is enforced per tool — `viewer`, `editor`, `admin`.

## Dashboards (8 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List every dashboard | `list all dashboards` | `list_dashboards` | viewer |
| Filter by category | `list AKS dashboards` · `list Loki dashboards` | `list_dashboards(tags=…)` | viewer |
| Search by title | `search dashboards postgres` | `search_dashboards` | viewer |
| Service-specific search | `payment-service dashboards` | `search_dashboards(query=svc)` | viewer |
| Multi-keyword fuzzy | `oracle kpi dashbords` (typo-tolerant) | local fuzzy + judge | viewer |
| Dashboard detail | `show dashboard <uid>` | `get_dashboard` | viewer |
| Panel inventory | `panels in <uid>` | `get_dashboard_panels` | viewer |
| Create empty dashboard | `create a dashboard called "X"` | `create_dashboard` | editor |
| Create smart dashboard | `create a payment-service dashboard` | `create_smart_dashboard` (metric-aware) | editor |
| Update dashboard | `update dashboard <uid> …` | `update_dashboard` | editor |
| Delete dashboard | `delete dashboard <uid>` | `delete_dashboard` | admin |

## Alerts (11 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List all rules | `list all alert rules` | `list_alert_rules` | viewer |
| Firing instances | `show firing alerts` | `list_alert_instances` | viewer |
| Explain a rule | `explain alert <uid>` · `why is <uid> firing?` | `get_alert_rule` | viewer |
| **Investigate** (compound) | `investigate alert <uid>` | `investigate_alert` — rule + firing + related dashboards + next steps | viewer |
| Create rule | `create alert rule …` | `create_alert_rule` | editor |
| Update rule | `update alert rule <uid> …` | `update_alert_rule` | editor |
| Delete rule | `delete alert rule <uid>` | `delete_alert_rule` | admin |
| Silence alert | `silence alert <uid>` | `silence_alert` | editor |
| List active silences | `list silences` | `list_silences` | viewer |
| Unmute | (tool) | `delete_silence` | editor |
| List contact points | `list contact points` | `list_contact_points` | viewer |
| List notification policies | `list notification policies` | `list_notification_policies` | viewer |
| List mute timings | `list mute timings` | `list_mute_timings` | viewer |

## Datasources & queries (8 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List datasources | `list datasources` | `list_datasources` | viewer |
| Datasource detail | `get datasource <uid>` | `get_datasource` | viewer |
| Generic query | `run promql <expr>` | `query_datasource` | viewer |
| List metric names | `list all metric names` | `list_metric_names` | viewer |
| Match metrics | `list metrics matching <regex>` | `list_metric_names(match=…)` | viewer |
| Label values | (tool) | `list_label_values` | viewer |
| LogQL | `search logs for <service>` | `query_loki` | viewer |
| TraceQL | `find slow traces for <service>` | `query_tempo` | viewer |

## Folders (5 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List folders | `list folders` | `list_folders` | viewer |
| Folder detail | (tool) | `get_folder` | viewer |
| Create folder | `create folder "My team"` | `create_folder` | editor |
| Rename folder | (tool) | `update_folder` | editor |
| Delete folder | (tool, destructive) | `delete_folder` | admin |

## Teams (4 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List teams | `list teams` | `list_teams` | viewer |
| Create team | `create team "Platform"` | `create_team` | admin |
| List members | (tool) | `list_team_members` | viewer |
| Add member | (tool) | `add_team_member` | admin |

## Plugins (2 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List plugins | `list all plugins` | `list_plugins` | viewer |
| Filter by type | `list datasource plugins` · `list panel plugins` | `list_plugins(type_filter=…)` | viewer |
| Plugin detail | (tool) | `get_plugin` | viewer |

## Library panels (2 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List reusable panels | `list library panels` | `list_library_panels` | viewer |
| Get panel model | (tool) | `get_library_panel` | viewer |

## Annotations (3 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List annotations | `list annotations` | `list_annotations` | viewer |
| Create annotation | (tool) | `create_annotation` | editor |
| Delete annotation | (tool) | `delete_annotation` | editor |

## Users / admin (2 tools)

| Use case | Example prompt | MCP tool | Role |
|---|---|---|---|
| List users | `list users` | `list_users` | admin |
| List service accounts | `list service accounts` | `list_service_accounts` | admin |

## Enterprise workflow tools (4 compound tools)

These chain multiple Grafana API calls into a single MCP round-trip, giving
the LLM structured investigation payloads instead of raw JSON dumps.

| Workflow | Example prompt | What it does |
|---|---|---|
| **Alert investigation** | `investigate alert <uid>` | Fetch rule → pull firing instances → find dashboards tagged with the rule's service → suggest LogQL / TraceQL next steps |
| **Multi-signal correlation** | `correlate service payment-service` | Query Prometheus / Loki / Tempo for the service in one call → return counts + error breadcrumbs |
| **SLO dashboard authoring** | `create slo dashboard for checkout-service` | 8-panel SLO tracking (SLI, error budget, fast + slow burn rate) with label-aware queries |
| **Metric impact analysis** | `which dashboards use metric http_requests_total` | Scans panel JSON across every dashboard — find out what breaks before renaming a metric |

## Authoring help (static, no tool call)

| Use case | Example prompt | Response |
|---|---|---|
| PromQL cookbook | `promql cookbook` | Copy-paste-ready patterns |
| LogQL cookbook | `logql examples` | Labels, JSON parsing, regex |
| TraceQL cookbook | `traceql templates` | Duration filters, service chaining |
| SLO authoring | `slo cheat sheet` | SLI/SLO/burn-rate recipe |
| Grafana navigation | `where do I find <feature>?` | UI map |
| Error decoder | `decode error: <msg>` | Common causes + fixes |

## Totals

- **~40 MCP tools** registered
- **60+ orchestrator intents** route natural language to those tools
- **LLM-as-judge** reranks fuzzy searches
- **4 enterprise workflow tools** for compound investigations
- **Per-role SA tokens** enforce RBAC at the MCP layer before Grafana ever sees the request

## Routing pipeline

```
user message
   │
   ▼
[0.5] mutation intents   (create/delete dashboard or folder)
[0]   explicit search
[1]   service-specific search                   (fuzzy + judge)
[2]   single-category dashboards
[3]   exact patterns  (25+ read, 10+ write, 4 workflows)
[4]   single-keyword category fallback
[5]   local fuzzy over every dashboard          (fuzzy + judge)
   │
   ▼
no match → LLM fallback with role-tuned prompt (PromQL help, chit-chat, incident analysis)
```

## Self-observability

The MCP server exports its own Prometheus metrics at `/metrics`:

- `ollychat_mcp_tool_calls_total{tool,role,status}` — counter
- `ollychat_mcp_tool_duration_seconds{tool,role}` — histogram
- `ollychat_mcp_grafana_requests_total{method,status_class}` — outbound Grafana API calls

Every tool call also emits a structured `tool.call` audit log line.
