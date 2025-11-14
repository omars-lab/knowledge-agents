"""
Unit tests for exception handlers (pure logic without external dependencies).
"""
from unittest.mock import MagicMock, patch

import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from knowledge_agents.types.response import WorkflowStepAnalysisResponse
from knowledge_agents.utils.exception_handlers import (
    GuardrailExceptionHandler,
    ServiceExceptionHandler,
    _record_exception_metrics,
)

pytestmark = [pytest.mark.unit]


def create_mock_response():
    """Create a mock response object for OpenAI exceptions."""
    mock_response = MagicMock()
    mock_response.request = MagicMock()
    return mock_response


class TestExceptionMetricsRecording:
    """Test exception metrics recording logic."""

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    @patch("knowledge_agents.utils.exception_handlers.get_settings")
    def test_record_rate_limit_metrics(self, mock_get_settings, mock_get_metrics):
        """Test metrics recording for rate limit errors."""
        mock_settings = MagicMock()
        mock_settings.openai_model = "gpt-4"
        mock_get_settings.return_value = mock_settings

        # Set up mock metric objects
        mock_guardrails_total = MagicMock()
        mock_openai_rate_limits = MagicMock()
        mock_request_error = MagicMock()

        mock_metrics = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.guardrails_total.labels.return_value = mock_guardrails_total
        mock_metrics.openai_rate_limits_total.labels.return_value = (
            mock_openai_rate_limits
        )
        mock_metrics.request_error_total.labels.return_value = mock_request_error
        mock_get_metrics.return_value = mock_metrics
        mock_get_metrics.return_value = mock_metrics

        exception = RateLimitError(
            "Rate limit exceeded", response=create_mock_response(), body=None
        )

        _record_exception_metrics(
            exception=exception,
            component="guardrail",
            component_type="workflow_detection",
        )

        # Verify guardrails_total metric was called with correct parameters
        mock_get_metrics.return_value.guardrails_total.labels.assert_called_with(
            guardrail_type="workflow_detection", result="error"
        )
        mock_guardrails_total.inc.assert_called_once()

        # Verify openai_rate_limits_total metric was called with correct parameters
        mock_get_metrics.return_value.openai_rate_limits_total.labels.assert_called_with(
            model="gpt-4", limit_type="requests"
        )
        mock_openai_rate_limits.inc.assert_called_once()

        # Verify request_error_total metric was called with correct parameters
        mock_get_metrics.return_value.request_error_total.labels.assert_called_with(
            component="guardrail", error_type="rate_limit"
        )
        mock_request_error.inc.assert_called_once()

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    @patch("knowledge_agents.utils.exception_handlers.get_settings")
    def test_record_authentication_metrics(self, mock_get_settings, mock_get_metrics):
        """Test metrics recording for authentication errors."""
        mock_settings = MagicMock()
        mock_settings.openai_model = "gpt-4"
        mock_get_settings.return_value = mock_settings

        exception = AuthenticationError(
            "Invalid API key", response=create_mock_response(), body=None
        )

        _record_exception_metrics(
            exception=exception, component="service", component_type="workflow_analysis"
        )

        # Verify guardrails_total metric
        mock_get_metrics.return_value.guardrails_total.labels.assert_called_with(
            guardrail_type="workflow_analysis", result="error"
        )

        # Verify request_error_total metric
        mock_get_metrics.return_value.request_error_total.labels.assert_called_with(
            component="service", error_type="authentication"
        )

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    @patch("knowledge_agents.utils.exception_handlers.get_settings")
    def test_record_connection_metrics(self, mock_get_settings, mock_get_metrics):
        """Test metrics recording for connection errors."""
        mock_settings = MagicMock()
        mock_settings.openai_model = "gpt-4"
        mock_get_settings.return_value = mock_settings

        exception = APIConnectionError(request=create_mock_response().request)

        _record_exception_metrics(
            exception=exception, component="guardrail", component_type="app_validation"
        )

        # Verify request_error_total metric
        mock_get_metrics.return_value.request_error_total.labels.assert_called_with(
            component="guardrail", error_type="connection"
        )

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    @patch("knowledge_agents.utils.exception_handlers.get_settings")
    def test_record_timeout_metrics(self, mock_get_settings, mock_get_metrics):
        """Test metrics recording for timeout errors."""
        mock_settings = MagicMock()
        mock_settings.openai_model = "gpt-4"
        mock_get_settings.return_value = mock_settings

        exception = APITimeoutError("Request timeout")

        _record_exception_metrics(
            exception=exception, component="service", component_type="workflow_analysis"
        )

        # Verify request_error_total metric
        mock_get_metrics.return_value.request_error_total.labels.assert_called_with(
            component="service", error_type="timeout"
        )

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    @patch("knowledge_agents.utils.exception_handlers.get_settings")
    def test_record_unexpected_metrics(self, mock_get_settings, mock_get_metrics):
        """Test metrics recording for unexpected errors."""
        mock_settings = MagicMock()
        mock_settings.openai_model = "gpt-4"
        mock_get_settings.return_value = mock_settings

        exception = ValueError("Unexpected error")

        _record_exception_metrics(
            exception=exception,
            component="guardrail",
            component_type="action_validation",
        )

        # Verify request_error_total metric
        mock_get_metrics.return_value.request_error_total.labels.assert_called_with(
            component="guardrail", error_type="unexpected"
        )

    @patch("knowledge_agents.utils.exception_handlers.get_metrics")
    def test_no_metrics_when_import_fails(self, mock_metrics):
        """Test graceful handling when metrics import fails."""
        with patch(
            "knowledge_agents.utils.exception_handlers.get_settings",
            side_effect=ImportError,
        ):
            exception = RateLimitError(
                "Rate limit exceeded", response=create_mock_response(), body=None
            )

            # Should not raise exception
            _record_exception_metrics(
                exception=exception,
                component="guardrail",
                component_type="workflow_detection",
            )


class TestGuardrailExceptionHandler:
    """Test guardrail exception handler logic."""

    def test_handle_rate_limit_exception(self):
        """Test guardrail exception handler for rate limit errors."""
        exception = RateLimitError(
            "Rate limit exceeded", response=create_mock_response(), body=None
        )

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = GuardrailExceptionHandler.handle_guardrail_exception(
                exception=exception,
                output_type=dict,  # Mock output type
                log_prefix="Test guardrail",
                guardrail_type="workflow_detection",
            )

            # Verify metrics were recorded
            mock_record.assert_called_once_with(
                exception=exception,
                component="guardrail",
                component_type="workflow_detection",
            )

            # Verify response structure
            assert "output_info" in result
            assert "tripwire_triggered" in result
            assert result["tripwire_triggered"] is True

    def test_handle_authentication_exception(self):
        """Test guardrail exception handler for authentication errors."""
        exception = AuthenticationError(
            "Invalid API key", response=create_mock_response(), body=None
        )

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = GuardrailExceptionHandler.handle_guardrail_exception(
                exception=exception,
                output_type=dict,
                log_prefix="Test guardrail",
                guardrail_type="app_validation",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="guardrail",
                component_type="app_validation",
            )

            assert result["tripwire_triggered"] is True

    def test_handle_connection_exception(self):
        """Test guardrail exception handler for connection errors."""
        exception = APIConnectionError(request=create_mock_response().request)

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = GuardrailExceptionHandler.handle_guardrail_exception(
                exception=exception,
                output_type=dict,
                log_prefix="Test guardrail",
                guardrail_type="action_validation",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="guardrail",
                component_type="action_validation",
            )

            assert result["tripwire_triggered"] is True

    def test_handle_unexpected_exception(self):
        """Test guardrail exception handler for unexpected errors."""
        exception = ValueError("Unexpected error")

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = GuardrailExceptionHandler.handle_guardrail_exception(
                exception=exception,
                output_type=dict,
                log_prefix="Test guardrail",
                guardrail_type="workflow_detection",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="guardrail",
                component_type="workflow_detection",
            )

            # Unexpected errors should fail open (tripwire=False)
            assert result["tripwire_triggered"] is False


class TestServiceExceptionHandler:
    """Test service exception handler logic."""

    def test_handle_rate_limit_exception(self):
        """Test service exception handler for rate limit errors."""
        exception = RateLimitError(
            "Rate limit exceeded", response=create_mock_response(), body=None
        )

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = ServiceExceptionHandler.handle_service_exception(
                exception=exception,
                response_type=WorkflowStepAnalysisResponse,
                log_prefix="Test service",
                service_type="workflow_analysis",
            )

            # Verify metrics were recorded
            mock_record.assert_called_once_with(
                exception=exception,
                component="service",
                component_type="workflow_analysis",
            )

            # Verify response structure
            assert isinstance(result, WorkflowStepAnalysisResponse)
            assert result.app is None
            assert result.action is None
            assert "rate limits" in result.reasoning
            assert result.workflow_step_detected is False
            assert "rate_limit_exceeded" in result.guardrails_tripped

    def test_handle_authentication_exception(self):
        """Test service exception handler for authentication errors."""
        exception = AuthenticationError(
            "Invalid API key", response=create_mock_response(), body=None
        )

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = ServiceExceptionHandler.handle_service_exception(
                exception=exception,
                response_type=WorkflowStepAnalysisResponse,
                log_prefix="Test service",
                service_type="workflow_analysis",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="service",
                component_type="workflow_analysis",
            )

            assert "Service configuration error" in result.reasoning
            assert "authentication_error" in result.guardrails_tripped

    def test_handle_timeout_exception(self):
        """Test service exception handler for timeout errors."""
        exception = APITimeoutError("Request timeout")

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = ServiceExceptionHandler.handle_service_exception(
                exception=exception,
                response_type=WorkflowStepAnalysisResponse,
                log_prefix="Test service",
                service_type="workflow_analysis",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="service",
                component_type="workflow_analysis",
            )

            assert "timeout" in result.reasoning
            assert "timeout" in result.guardrails_tripped

    def test_handle_connection_exception(self):
        """Test service exception handler for connection errors."""
        exception = APIConnectionError(request=create_mock_response().request)

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = ServiceExceptionHandler.handle_service_exception(
                exception=exception,
                response_type=WorkflowStepAnalysisResponse,
                log_prefix="Test service",
                service_type="workflow_analysis",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="service",
                component_type="workflow_analysis",
            )

            assert "unavailable" in result.reasoning
            assert "connection_error" in result.guardrails_tripped

    def test_handle_unexpected_exception(self):
        """Test service exception handler for unexpected errors."""
        exception = ValueError("Unexpected error")

        with patch(
            "knowledge_agents.utils.exception_handlers._record_exception_metrics"
        ) as mock_record:
            result = ServiceExceptionHandler.handle_service_exception(
                exception=exception,
                response_type=WorkflowStepAnalysisResponse,
                log_prefix="Test service",
                service_type="workflow_analysis",
            )

            mock_record.assert_called_once_with(
                exception=exception,
                component="service",
                component_type="workflow_analysis",
            )

            assert "Error in service" in result.reasoning
            assert "analysis_error" in result.guardrails_tripped
