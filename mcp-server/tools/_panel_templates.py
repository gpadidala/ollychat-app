"""RED + resource panel generator shared by create_smart_dashboard."""
from __future__ import annotations


def _regex_for_topic(topic: str) -> str:
    t = topic.strip().lower()
    variants = {t, t.replace(" ", "-"), t.replace(" ", "_"), t.replace("-", "_"), t.replace("-", " ")}
    variants = {v for v in variants if v and v not in {"the", "a", "an"}}
    parts = "|".join(sorted(variants, key=len, reverse=True))
    return f".*({parts}).*"


def _grid(x: int, y: int, w: int = 12, h: int = 8) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def _ts(pid: int, title: str, ds_uid: str, expr: str, pos: dict, unit: str = "short", legend: str = "{{service}}") -> dict:
    return {
        "id": pid,
        "type": "timeseries",
        "title": title,
        "datasource": {"type": "prometheus", "uid": ds_uid},
        "gridPos": pos,
        "targets": [
            {"refId": "A", "expr": expr, "legendFormat": legend, "datasource": {"type": "prometheus", "uid": ds_uid}},
        ],
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"lineWidth": 2, "fillOpacity": 10}}, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
    }


def _stat(pid: int, title: str, ds_uid: str, expr: str, pos: dict, unit: str = "short") -> dict:
    return {
        "id": pid,
        "type": "stat",
        "title": title,
        "datasource": {"type": "prometheus", "uid": ds_uid},
        "gridPos": pos,
        "targets": [{"refId": "A", "expr": expr, "datasource": {"type": "prometheus", "uid": ds_uid}, "legendFormat": ""}],
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"colorMode": "value", "graphMode": "area", "reduceOptions": {"values": False, "calcs": ["lastNotNull"]}},
    }


def _row(pid: int, title: str, y: int) -> dict:
    return {
        "id": pid, "type": "row", "title": title, "collapsed": False,
        "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": [],
    }


def build_red_panels(topic: str, ds_uid: str) -> list[dict]:
    """14 panels covering RED + resources + saturation, filtered by topic label regex."""
    rx = _regex_for_topic(topic)
    panels: list[dict] = []
    pid = 1

    panels.append(_row(pid, f"{topic.title()} — Request Health (RED)", 0)); pid += 1
    panels.append(_stat(
        pid, "Requests / sec (now)", ds_uid,
        f'sum(rate(http_requests_total{{service=~"{rx}"}}[5m]))',
        _grid(0, 1, 6, 4), unit="reqps",
    )); pid += 1
    panels.append(_stat(
        pid, "Error rate % (5m)", ds_uid,
        f'100 * sum(rate(http_requests_total{{service=~"{rx}", status=~"5.."}}[5m])) / '
        f'clamp_min(sum(rate(http_requests_total{{service=~"{rx}"}}[5m])), 0.001)',
        _grid(6, 1, 6, 4), unit="percent",
    )); pid += 1
    panels.append(_stat(
        pid, "p95 latency (ms)", ds_uid,
        f'1000 * histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{service=~"{rx}"}}[5m])))',
        _grid(12, 1, 6, 4), unit="ms",
    )); pid += 1
    panels.append(_stat(
        pid, "p99 latency (ms)", ds_uid,
        f'1000 * histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{{service=~"{rx}"}}[5m])))',
        _grid(18, 1, 6, 4), unit="ms",
    )); pid += 1

    panels.append(_ts(
        pid, "Request rate by service", ds_uid,
        f'sum by (service) (rate(http_requests_total{{service=~"{rx}"}}[5m]))',
        _grid(0, 5, 12, 8), unit="reqps",
    )); pid += 1
    panels.append(_ts(
        pid, "Error rate by service (5xx)", ds_uid,
        f'sum by (service) (rate(http_requests_total{{service=~"{rx}", status=~"5.."}}[5m]))',
        _grid(12, 5, 12, 8), unit="reqps",
    )); pid += 1
    panels.append(_ts(
        pid, "Latency — p50 / p95 / p99", ds_uid,
        f'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{service=~"{rx}"}}[5m])))',
        _grid(0, 13, 24, 8), unit="s", legend="p95",
    )); pid += 1

    panels.append(_row(pid, f"{topic.title()} — Resource Usage", 21)); pid += 1
    panels.append(_ts(
        pid, "CPU usage by pod", ds_uid,
        f'sum by (pod) (rate(container_cpu_usage_seconds_total{{pod=~"{rx}"}}[5m]))',
        _grid(0, 22, 12, 8), unit="short", legend="{{pod}}",
    )); pid += 1
    panels.append(_ts(
        pid, "Memory usage by pod", ds_uid,
        f'sum by (pod) (container_memory_working_set_bytes{{pod=~"{rx}"}})',
        _grid(12, 22, 12, 8), unit="bytes", legend="{{pod}}",
    )); pid += 1

    panels.append(_row(pid, f"{topic.title()} — Saturation", 30)); pid += 1
    panels.append(_ts(
        pid, "In-flight requests", ds_uid,
        f'sum by (service) (http_requests_in_flight{{service=~"{rx}"}})',
        _grid(0, 31, 12, 8), unit="short",
    )); pid += 1
    panels.append(_ts(
        pid, "Request size p95 (bytes)", ds_uid,
        f'histogram_quantile(0.95, sum by (le) (rate(http_request_size_bytes_bucket{{service=~"{rx}"}}[5m])))',
        _grid(12, 31, 12, 8), unit="bytes",
    ))
    return panels
