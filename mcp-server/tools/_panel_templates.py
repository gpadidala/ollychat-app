"""RED + resource panel generator shared by create_smart_dashboard.

Two modes:
- build_red_panels(topic, ds_uid)            — template mode (keeps old path alive)
- build_panels_from_metrics(topic, ds_uid,   — discovery mode: builds panels
                            metric_names)     using actual metric names the
                                              Prometheus datasource exposes
"""
from __future__ import annotations

from typing import Iterable


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


# ═════════════════════════════════════════════════════════════════
# Discovery-aware panel builder — uses metric names that actually
# exist in the datasource so panels never show "No data" when real
# metrics are flowing.
# ═════════════════════════════════════════════════════════════════


def _categorize_metrics(names: Iterable[str]) -> dict[str, list[str]]:
    """Split discovered metric names into buckets by naming convention."""
    buckets = {
        "histogram_bucket": [],  # _bucket → quantiles
        "counter": [],           # _total / _count → rate
        "gauge_seconds": [],     # _seconds, _duration → latency gauge
        "gauge_bytes": [],       # _bytes → memory/size
        "gauge_generic": [],     # anything else
    }
    seen: set[str] = set()
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        low = n.lower()
        if n.endswith("_bucket"):
            buckets["histogram_bucket"].append(n)
        elif n.endswith("_total") or n.endswith("_count"):
            buckets["counter"].append(n)
        elif "duration" in low or low.endswith("_seconds"):
            buckets["gauge_seconds"].append(n)
        elif low.endswith("_bytes"):
            buckets["gauge_bytes"].append(n)
        else:
            buckets["gauge_generic"].append(n)
    return buckets


def _histogram_base(bucket_name: str) -> str:
    return bucket_name[: -len("_bucket")] if bucket_name.endswith("_bucket") else bucket_name


def build_panels_from_metrics(
    topic: str,
    ds_uid: str,
    metric_names: list[str],
) -> list[dict]:
    """Build panels using the real metric names discovered in the datasource.

    Falls back to the template RED panels if ``metric_names`` is empty.
    """
    if not metric_names:
        return build_red_panels(topic, ds_uid)

    cats = _categorize_metrics(metric_names)
    panels: list[dict] = []
    pid = 1
    y = 0

    # Header row
    panels.append(_row(pid, f"{topic.title()} — Overview ({len(metric_names)} metrics)", y))
    pid += 1
    y += 1

    # Stat: count of matching metrics (guaranteed to render)
    panels.append(_stat(
        pid, "Metrics matched", ds_uid,
        f'count(group by (__name__) ({{__name__=~".*({topic}).*"}}))',
        _grid(0, y, 6, 4), unit="short",
    ))
    pid += 1

    # Stat: first three counters as "events / sec"
    for i, mn in enumerate(cats["counter"][:3]):
        panels.append(_stat(
            pid, f"{_clean_label(mn)} / sec", ds_uid,
            f"sum(rate({mn}[5m]))",
            _grid(6 + i * 6, y, 6, 4), unit="short",
        ))
        pid += 1
    y += 4

    # Row: Rate (counters)
    if cats["counter"]:
        panels.append(_row(pid, "Rates (counters)", y)); pid += 1; y += 1
        for i, mn in enumerate(cats["counter"][:4]):
            panels.append(_ts(
                pid, f"rate({mn}[5m])", ds_uid,
                f"sum by (instance) (rate({mn}[5m]))",
                _grid((i % 2) * 12, y + (i // 2) * 8, 12, 8), unit="short", legend="{{instance}}",
            ))
            pid += 1
        y += ((len(cats["counter"][:4]) + 1) // 2) * 8

    # Row: Latency quantiles from histograms
    if cats["histogram_bucket"]:
        panels.append(_row(pid, "Latency quantiles (histograms)", y)); pid += 1; y += 1
        for i, mn in enumerate(cats["histogram_bucket"][:4]):
            base = _histogram_base(mn)
            panels.append(_ts(
                pid, f"p50/p95/p99 — {_clean_label(base)}", ds_uid,
                f"histogram_quantile(0.95, sum by (le) (rate({mn}[5m])))",
                _grid((i % 2) * 12, y + (i // 2) * 8, 12, 8), unit="s", legend="p95",
            ))
            pid += 1
        y += ((len(cats["histogram_bucket"][:4]) + 1) // 2) * 8

    # Row: Gauges (seconds / bytes / generic)
    gauges = cats["gauge_seconds"] + cats["gauge_bytes"] + cats["gauge_generic"]
    if gauges:
        panels.append(_row(pid, "Gauges & samples", y)); pid += 1; y += 1
        for i, mn in enumerate(gauges[:4]):
            unit = "bytes" if mn.endswith("_bytes") else ("s" if mn in cats["gauge_seconds"] else "short")
            panels.append(_ts(
                pid, _clean_label(mn), ds_uid,
                f"sum by (instance) ({mn})",
                _grid((i % 2) * 12, y + (i // 2) * 8, 12, 8), unit=unit, legend="{{instance}}",
            ))
            pid += 1
        y += ((len(gauges[:4]) + 1) // 2) * 8

    # Row: raw inventory — always renders, great for debugging
    panels.append(_row(pid, "Metric inventory (all matched names)", y)); pid += 1; y += 1
    panels.append(_ts(
        pid, "Top series count per metric", ds_uid,
        f'topk(20, count by (__name__) ({{__name__=~".*({topic}).*"}}))',
        _grid(0, y, 24, 8), unit="short", legend="{{__name__}}",
    ))

    return panels


def _clean_label(metric_name: str) -> str:
    """Shorten a metric name for a panel title."""
    n = metric_name
    for suf in ("_total", "_count", "_seconds", "_bytes", "_bucket", "_sum"):
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    return n.replace("_", " ")
