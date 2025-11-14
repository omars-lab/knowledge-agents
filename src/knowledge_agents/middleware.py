"""Middleware for the Agentic API."""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    def __init__(self, app, metrics):
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(self, request: Request, call_next):
        """Process HTTP request and collect metrics."""
        start_time = time.time()

        # Extract method and path
        method = request.method
        path = request.url.path

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Record metrics
        self.metrics.http_requests_total.labels(
            method=method, endpoint=path, status=response.status_code
        ).inc()
        self.metrics.http_request_duration.labels(method=method, endpoint=path).observe(
            duration
        )

        # Record request success/error metrics
        if 200 <= response.status_code < 400:
            self.metrics.request_success_total.labels(
                endpoint=path, status_code=str(response.status_code)
            ).inc()
        else:
            error_type = (
                "client_error" if 400 <= response.status_code < 500 else "server_error"
            )
            self.metrics.request_error_total.labels(
                component="api", error_type=error_type
            ).inc()

        # Record end-to-end duration
        self.metrics.end_to_end_duration.labels(endpoint=path).observe(duration)

        return response
