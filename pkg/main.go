package main

import (
	"os"

	"github.com/grafana/grafana-plugin-sdk-go/backend/app"
	"github.com/grafana/grafana-plugin-sdk-go/backend/log"
	"github.com/gopal/ollychat-app/pkg/plugin"
)

func main() {
	if err := app.Manage("gopal-ollychat-app", plugin.NewApp, app.ManageOpts{}); err != nil {
		log.DefaultLogger.Error("Error starting OllyChat plugin", "error", err.Error())
		os.Exit(1)
	}
}
