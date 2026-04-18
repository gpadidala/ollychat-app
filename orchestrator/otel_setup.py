"""OpenTelemetry initialization for the OllyChat orchestrator.

Adapted from llm-o11y-platform/src/otel/setup.py — emits traces and metrics
to an OTEL collector (Grafana Alloy) for visualization in Tempo/Mimir.
"""
from __future__ import annotations

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_otel(settings) -> None:
    """Initialize OpenTelemetry with OTLP gRPC exporters."""
    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.namespace": "ollychat",
        "deployment.environment": "production",
    })

    # --- Traces ---
    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel_exporter_endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # --- Register instruments ---
    meter = metrics.get_meter("ollychat-orchestrator")

    # LLM metrics
    meter.create_counter("ollychat_requests_total", description="Total LLM requests")
    meter.create_counter("ollychat_tokens_total", description="Total tokens used")
    meter.create_counter("ollychat_cost_usd_total", description="Total cost in USD")
    meter.create_histogram("ollychat_request_duration_seconds", description="LLM request latency")
    meter.create_histogram("ollychat_ttft_seconds", description="Time to first token")

    # MCP metrics
    meter.create_counter("ollychat_mcp_tool_calls_total", description="Total MCP tool invocations")
    meter.create_histogram("ollychat_mcp_tool_duration_seconds", description="MCP tool latency")
    meter.create_up_down_counter("ollychat_mcp_sessions_active", description="Active MCP sessions")

    # PII metrics
    meter.create_counter("ollychat_pii_detections_total", description="PII detections by type")

    # Investigation metrics
    meter.create_counter("ollychat_investigations_total", description="Total investigations")
    meter.create_histogram("ollychat_investigation_duration_seconds", description="Investigation duration")

    # Session metrics
    meter.create_up_down_counter("ollychat_sessions_active", description="Active chat sessions")
    meter.create_counter("ollychat_messages_total", description="Total chat messages")
