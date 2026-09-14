"""Métricas en memoria (exportables vía /metrics)."""
from __future__ import annotations

from collections import defaultdict
from threading import Lock

from src.domain.ports.metrics_port import MetricsPort


class InMemoryMetrics(MetricsPort):
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"

    def incr(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self._counters[self._key(name, labels)] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._histograms[self._key(name, labels)].append(float(value))

    def gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = float(value)

    def snapshot(self) -> dict:
        with self._lock:
            hist = {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "avg": (sum(v) / len(v)) if v else 0.0,
                }
                for k, v in self._histograms.items()
            }
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": hist,
            }

    def render_prometheus(self) -> str:
        snap = self.snapshot()
        lines: list[str] = []
        for k, v in snap["counters"].items():
            lines.append(f"{k} {v}")
        for k, v in snap["gauges"].items():
            lines.append(f"{k} {v}")
        for k, stats in snap["histograms"].items():
            base = k.split("{", 1)[0]
            labels = ""
            if "{" in k:
                labels = "{" + k.split("{", 1)[1]
            lines.append(f"{base}_count{labels} {stats['count']}")
            lines.append(f"{base}_sum{labels} {stats['sum']}")
        return "\n".join(lines) + "\n"
