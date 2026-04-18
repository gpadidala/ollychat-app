package plugin

import (
	"io"
	"net/http"

	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
)

// handleChat proxies chat requests to the orchestrator with SSE streaming support.
// This is the primary endpoint -- it streams LLM responses back to the UI.
func (a *App) handleChat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	a.mu.RLock()
	targetURL := a.orchestratorURL + "/api/v1/chat"
	a.mu.RUnlock()

	// Forward the request to the orchestrator
	proxyReq, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
	if err != nil {
		log.DefaultLogger.Error("Failed to create proxy request", "error", err)
		http.Error(w, "Internal error", http.StatusInternalServerError)
		return
	}

	// Copy headers and add Grafana context
	proxyReq.Header.Set("Content-Type", "application/json")
	proxyReq.Header.Set("Accept", "text/event-stream")
	if user := r.Header.Get("X-Grafana-User"); user != "" {
		proxyReq.Header.Set("X-Grafana-User", user)
	}
	if orgID := r.Header.Get("X-Grafana-Org-Id"); orgID != "" {
		proxyReq.Header.Set("X-Grafana-Org-Id", orgID)
	}

	// Execute request
	resp, err := a.httpClient.Do(proxyReq)
	if err != nil {
		log.DefaultLogger.Error("Orchestrator request failed", "error", err)
		http.Error(w, "Orchestrator unreachable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	// Set SSE headers for streaming
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(resp.StatusCode)

	// Stream the response
	flusher, canFlush := w.(http.Flusher)
	buf := make([]byte, 4096)
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, writeErr := w.Write(buf[:n]); writeErr != nil {
				log.DefaultLogger.Debug("Client disconnected during stream")
				return
			}
			if canFlush {
				flusher.Flush()
			}
		}
		if readErr != nil {
			if readErr != io.EOF {
				log.DefaultLogger.Error("Error reading orchestrator response", "error", readErr)
			}
			return
		}
	}
}

// handleProxy creates a generic proxy handler for non-streaming endpoints.
func (a *App) handleProxy(path string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		a.mu.RLock()
		targetURL := a.orchestratorURL + path
		a.mu.RUnlock()

		proxyReq, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, r.Body)
		if err != nil {
			log.DefaultLogger.Error("Failed to create proxy request", "path", path, "error", err)
			http.Error(w, "Internal error", http.StatusInternalServerError)
			return
		}

		proxyReq.Header.Set("Content-Type", r.Header.Get("Content-Type"))
		if user := r.Header.Get("X-Grafana-User"); user != "" {
			proxyReq.Header.Set("X-Grafana-User", user)
		}
		if orgID := r.Header.Get("X-Grafana-Org-Id"); orgID != "" {
			proxyReq.Header.Set("X-Grafana-Org-Id", orgID)
		}

		resp, err := a.httpClient.Do(proxyReq)
		if err != nil {
			log.DefaultLogger.Error("Orchestrator request failed", "path", path, "error", err)
			http.Error(w, "Orchestrator unreachable", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		// Copy response headers
		for key, values := range resp.Header {
			for _, v := range values {
				w.Header().Add(key, v)
			}
		}
		w.WriteHeader(resp.StatusCode)

		if _, err := io.Copy(w, resp.Body); err != nil {
			log.DefaultLogger.Debug("Error copying response body", "error", err)
		}
	}
}
