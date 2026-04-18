.PHONY: all build dev up down test lint clean install

# ─────────────────────────────────────────────────────────
# OllyChat Grafana App Plugin — Build & Deploy
# ─────────────────────────────────────────────────────────

all: install build

# Install all dependencies
install:
	npm install
	cd orchestrator && pip install -r requirements.txt

# Build frontend + backend plugin
build: build-frontend build-backend

build-frontend:
	npm run build

build-backend:
	@echo "Building Go backend for linux/amd64..."
	GOOS=linux GOARCH=amd64 go build -o dist/gpx_ollychat_linux_amd64 ./pkg
	@echo "Building Go backend for darwin/arm64..."
	GOOS=darwin GOARCH=arm64 go build -o dist/gpx_ollychat_darwin_arm64 ./pkg

# Development mode
dev:
	npm run dev &
	cd orchestrator && python main.py &
	@echo "Frontend dev server + Orchestrator running"

# Docker Compose
up:
	docker compose up -d
	@echo ""
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║  OllyChat is running!                               ║"
	@echo "║                                                     ║"
	@echo "║  Grafana:       http://localhost:3000                ║"
	@echo "║  Orchestrator:  http://localhost:8000                ║"
	@echo "║  OllyChat:      http://localhost:3000/a/gopal-ollychat-app/chat  ║"
	@echo "║                                                     ║"
	@echo "║  Grafana Login:  admin / admin                      ║"
	@echo "╚══════════════════════════════════════════════════════╝"

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart ollychat-orchestrator

# Testing
test: test-frontend test-orchestrator

test-frontend:
	npm run test

test-orchestrator:
	cd orchestrator && python -m pytest tests/ -v

# Linting
lint:
	npm run lint
	npm run typecheck
	cd orchestrator && ruff check .

# Clean build artifacts
clean:
	rm -rf dist/ node_modules/ orchestrator/__pycache__

# Show help
help:
	@echo "Available targets:"
	@echo "  make install    - Install all dependencies"
	@echo "  make build      - Build frontend + Go backend"
	@echo "  make dev        - Start development servers"
	@echo "  make up         - Start all services via Docker Compose"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - Tail Docker Compose logs"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linters"
	@echo "  make clean      - Remove build artifacts"
