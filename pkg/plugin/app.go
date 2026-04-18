package plugin

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"
	"time"

	"github.com/grafana/grafana-plugin-sdk-go/backend"
	"github.com/grafana/grafana-plugin-sdk-go/backend/instancemgmt"
	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
	"github.com/grafana/grafana-plugin-sdk-go/backend/resource/httpadapter"
)

// App is the main OllyChat app plugin instance.
type App struct {
	httpClient      *http.Client
	orchestratorURL string
	mu              sync.RWMutex
}

// AppSettings holds the plugin's JSON configuration.
type AppSettings struct {
	OrchestratorURL string `json:"orchestratorUrl"`
	DefaultModel    string `json:"defaultModel"`
	EnablePII       bool   `json:"enablePII"`
	EnableCost      bool   `json:"enableCostTracking"`
}

// NewApp creates a new OllyChat app instance. Called by the Grafana plugin SDK.
func NewApp(_ context.Context, settings backend.AppInstanceSettings) (instancemgmt.Instance, error) {
	a := &App{
		httpClient: &http.Client{
			Timeout: 120 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 20,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		orchestratorURL: "http://localhost:8000",
	}

	// Parse settings from Grafana plugin config
	if len(settings.JSONData) > 0 {
		var appSettings AppSettings
		if err := json.Unmarshal(settings.JSONData, &appSettings); err != nil {
			log.DefaultLogger.Warn("Failed to parse plugin settings, using defaults", "error", err)
		} else {
			if appSettings.OrchestratorURL != "" {
				a.orchestratorURL = appSettings.OrchestratorURL
			}
		}
	}

	log.DefaultLogger.Info("OllyChat plugin initialized", "orchestratorUrl", a.orchestratorURL)
	return a, nil
}

// Dispose cleans up resources when the plugin is unloaded.
func (a *App) Dispose() {
	a.httpClient.CloseIdleConnections()
}

// CallResource handles HTTP requests from the Grafana frontend.
// It proxies requests to the Python orchestrator with OTEL context and user info.
func (a *App) CallResource(ctx context.Context, req *backend.CallResourceRequest, sender backend.CallResourceResponseSender) error {
	handler := httpadapter.New(a.resourceHandler())
	return handler.CallResource(ctx, req, sender)
}

// resourceHandler returns the HTTP mux for the plugin's resource API.
func (a *App) resourceHandler() http.Handler {
	mux := http.NewServeMux()

	// Chat endpoint - proxies to orchestrator with SSE streaming
	mux.HandleFunc("/api/v1/chat", a.handleChat)

	// Models endpoint - list available LLM models
	mux.HandleFunc("/api/v1/models", a.handleProxy("/api/v1/models"))

	// Health endpoint
	mux.HandleFunc("/api/v1/health", a.handleProxy("/api/v1/health"))

	// MCP endpoints
	mux.HandleFunc("/api/v1/mcp/servers", a.handleProxy("/api/v1/mcp/servers"))
	mux.HandleFunc("/api/v1/mcp/tools", a.handleProxy("/api/v1/mcp/tools"))
	mux.HandleFunc("/api/v1/mcp/tools/call", a.handleProxy("/api/v1/mcp/tools/call"))

	// Investigation endpoints
	mux.HandleFunc("/api/v1/investigate", a.handleProxy("/api/v1/investigate"))

	// Skills endpoints
	mux.HandleFunc("/api/v1/skills", a.handleProxy("/api/v1/skills"))

	// Rules endpoints
	mux.HandleFunc("/api/v1/rules", a.handleProxy("/api/v1/rules"))

	return mux
}

// CheckHealth returns the health status of the plugin.
func (a *App) CheckHealth(ctx context.Context, req *backend.CheckHealthRequest) (*backend.CheckHealthResult, error) {
	a.mu.RLock()
	url := a.orchestratorURL
	a.mu.RUnlock()

	healthReq, err := http.NewRequestWithContext(ctx, http.MethodGet, url+"/api/v1/health", nil)
	if err != nil {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: "Failed to create health check request: " + err.Error(),
		}, nil
	}

	resp, err := a.httpClient.Do(healthReq)
	if err != nil {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: "Orchestrator unreachable at " + url + ": " + err.Error(),
		}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return &backend.CheckHealthResult{
			Status:  backend.HealthStatusError,
			Message: "Orchestrator returned status " + resp.Status,
		}, nil
	}

	return &backend.CheckHealthResult{
		Status:  backend.HealthStatusOk,
		Message: "OllyChat orchestrator is healthy",
	}, nil
}
