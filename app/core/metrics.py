"""Per-application Prometheus metrics with bounded route and method labels."""

import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HTTPMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        PlatformCollector(registry=self.registry)
        ProcessCollector(registry=self.registry)
        self.requests = Counter(
            "http_requests_total",
            "Total HTTP requests handled",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration including response streaming",
            ["method", "endpoint"],
            registry=self.registry,
        )


class PrometheusMetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: HTTPMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in {"/metrics", "/healthz", "/readyz"}:
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def record_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        finally:
            # FastAPI's included-router context preserves prefixes; the original
            # route alone can contain only '/{document_id}' on the pinned version.
            route = scope.get("fastapi", {}).get("effective_route_context") or scope.get("route")
            endpoint = getattr(route, "path_format", None) or getattr(route, "path", "unmatched")
            method = scope["method"]
            if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"}:
                method = "OTHER"
            self.metrics.requests.labels(method, endpoint, str(status)).inc()
            self.metrics.duration.labels(method, endpoint).observe(time.perf_counter() - started)
