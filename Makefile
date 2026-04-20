.PHONY: help up down restart rebuild reset logs status test clean dev build install

# ─────────────────────────────────────────────────────────
# O11yBot — all-in-one Grafana chatbot stack
# ─────────────────────────────────────────────────────────

help:   ## Show this help
	@echo ""
	@echo "O11yBot — Grafana AI assistant"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / { printf "  make %-12s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

up:     ## Boot everything — Grafana + 113 dashboards + MCP + orchestrator + LGTM + Ollama
	@test -f .env || (cp .env.example .env && echo "  ✓ Created .env from .env.example")
	docker compose up -d --build
	@echo "  · bootstrapping Grafana service-account tokens (idempotent)…"
	@./scripts/bootstrap-tokens.sh
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║  O11yBot is up — zero manual setup                           ║"
	@echo "║                                                              ║"
	@echo "║  Grafana UI       http://localhost:3002  (admin / admin)     ║"
	@echo "║  Orchestrator API http://localhost:8000                      ║"
	@echo "║  MCP server       http://localhost:8765/health               ║"
	@echo "║  Ollama           http://localhost:11434                     ║"
	@echo "║                                                              ║"
	@echo "║  113 dashboards provisioned · 53 MCP tools online · $0 LLM   ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@$(MAKE) --no-print-directory status

down:   ## Stop all services (keeps data volumes)
	docker compose down

restart: ## Stop + boot
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up

rebuild: ## Rebuild images without cache + boot
	docker compose build --no-cache
	docker compose up -d

reset:  ## DANGER: drop all data volumes + rebuild from scratch
	docker compose down -v
	docker compose up -d --build

logs:   ## Tail every service's logs
	docker compose logs -f

status: ## Print service health
	@echo ""
	@echo "=== Service status ==="
	@docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null || echo "stack is down"
	@echo ""

test:   ## Run the full 160-test suite
	cd tests && ./preflight.sh && ./run-all-tests.sh

clean:  ## Remove built artefacts (dist/, __pycache__, .pyc)
	rm -rf dist/gpx_*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ── Dev helpers ─────────────────────────────────────────────
dev:    ## Run widget hot-reload + orchestrator locally (not via docker)
	npm run dev & \
	cd orchestrator && python main.py

build:  ## Build the plugin assets into dist/
	npm run build

install: ## Install JS + Python deps on the host (for non-docker dev)
	npm install
	cd orchestrator && pip install -r requirements.txt
	cd mcp-server && pip install -r requirements.txt
