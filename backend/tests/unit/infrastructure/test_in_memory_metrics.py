"""Cobertura de métricas en memoria y ramas Prometheus."""
from __future__ import annotations

from src.infrastructure.metrics.in_memory_metrics import InMemoryMetrics


def test_metrics_snapshot_and_prometheus_render():
    m = InMemoryMetrics()
    m.incr("requests_total", task="analyze")
    m.incr("requests_total", value=2.0, task="ask")
    m.gauge("queue_depth", 3.0, worker="outbox")
    m.observe("latency_ms", 12.5, route="/analyze")
    m.observe("latency_ms", 7.5, route="/analyze")

    snap = m.snapshot()
    assert snap["histograms"]
    assert snap["gauges"]

    text = m.render_prometheus()
    assert "requests_total" in text
    assert "queue_depth" in text
    assert "latency_ms_count" in text
    assert "latency_ms_sum" in text


def test_metrics_key_without_labels():
    m = InMemoryMetrics()
    m.incr("plain_counter")
    assert "plain_counter" in m.snapshot()["counters"]
