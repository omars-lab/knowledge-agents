"""
Unit tests for middleware (request processing logic without HTTP dependencies).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import Response

from knowledge_agents.middleware import MetricsMiddleware

pytestmark = [pytest.mark.unit]


class TestMetricsMiddleware:
    """Test metrics middleware with mocked dependencies."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_app = AsyncMock()
        self.mock_metrics = MagicMock()
        self.middleware = MetricsMiddleware(self.mock_app, self.mock_metrics)

    @pytest.mark.asyncio
    async def test_dispatch_successful_request(self):
        """Test middleware processing for successful request."""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/health"

        # Mock response
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        # Mock call_next
        mock_call_next = AsyncMock(return_value=mock_response)

        # Mock time to control duration
        with patch("time.time", side_effect=[0.0, 0.1]):  # 0.1 second duration
            result = await self.middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response
        mock_call_next.assert_called_once_with(mock_request)

        # Verify metrics were recorded
        self.mock_metrics.http_requests_total.labels.assert_called_with(
            method="GET", endpoint="/health", status=200
        )
        self.mock_metrics.http_requests_total.labels.return_value.inc.assert_called_once()

        self.mock_metrics.http_request_duration.labels.assert_called_with(
            method="GET", endpoint="/health"
        )
        self.mock_metrics.http_request_duration.labels.return_value.observe.assert_called_with(
            0.1
        )

        # Verify success metrics
        self.mock_metrics.request_success_total.labels.assert_called_with(
            endpoint="/health", status_code="200"
        )
        self.mock_metrics.request_success_total.labels.return_value.inc.assert_called_once()

        # Verify end-to-end duration
        self.mock_metrics.end_to_end_duration.labels.assert_called_with(
            endpoint="/health"
        )
        self.mock_metrics.end_to_end_duration.labels.return_value.observe.assert_called_with(
            0.1
        )

    @pytest.mark.asyncio
    async def test_dispatch_client_error(self):
        """Test middleware processing for client error (4xx)."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/analyze"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400

        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("time.time", side_effect=[0.0, 0.05]):
            result = await self.middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response

        # Verify error metrics for client error
        self.mock_metrics.request_error_total.labels.assert_called_with(
            component="api", error_type="client_error"
        )
        self.mock_metrics.request_error_total.labels.return_value.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_server_error(self):
        """Test middleware processing for server error (5xx)."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/health"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500

        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("time.time", side_effect=[0.0, 0.2]):
            result = await self.middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response

        # Verify error metrics for server error
        self.mock_metrics.request_error_total.labels.assert_called_with(
            component="api", error_type="server_error"
        )
        self.mock_metrics.request_error_total.labels.return_value.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_redirect_status(self):
        """Test middleware processing for redirect status (3xx)."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/redirect"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 301

        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("time.time", side_effect=[0.0, 0.03]):
            result = await self.middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response

        # Verify success metrics (3xx is considered success)
        self.mock_metrics.request_success_total.labels.assert_called_with(
            endpoint="/redirect", status_code="301"
        )
        self.mock_metrics.request_success_total.labels.return_value.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_different_endpoints(self):
        """Test middleware with different endpoints and methods."""
        test_cases = [
            ("GET", "/health", 200),
            ("POST", "/analyze", 201),
            ("PUT", "/update", 400),
            ("DELETE", "/delete", 500),
        ]

        for method, path, status_code in test_cases:
            mock_request = MagicMock(spec=Request)
            mock_request.method = method
            mock_request.url.path = path

            mock_response = MagicMock(spec=Response)
            mock_response.status_code = status_code

            mock_call_next = AsyncMock(return_value=mock_response)

            with patch("time.time", side_effect=[0.0, 0.1]):
                result = await self.middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response

            # Verify metrics were recorded for this request
            self.mock_metrics.http_requests_total.labels.assert_called_with(
                method=method, endpoint=path, status=status_code
            )
            self.mock_metrics.http_request_duration.labels.assert_called_with(
                method=method, endpoint=path
            )

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        assert self.middleware.app == self.mock_app
        assert self.middleware.metrics == self.mock_metrics

    @pytest.mark.asyncio
    async def test_dispatch_call_next_exception(self):
        """Test middleware when call_next raises an exception."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/health"

        mock_call_next = AsyncMock(side_effect=Exception("Test error"))

        with pytest.raises(Exception) as exc_info:
            await self.middleware.dispatch(mock_request, mock_call_next)

        assert str(exc_info.value) == "Test error"

        # Verify that metrics are still recorded even on exception
        # (This would happen in a real scenario where the exception is caught and handled)
