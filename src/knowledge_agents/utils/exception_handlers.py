"""
Centralized exception handling utilities for OpenAI API calls
"""
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from ..config.api_config import get_settings as _get_settings
from ..metrics import metrics as _metrics

logger = logging.getLogger(__name__)


def get_settings():
    """Get settings instance - imported from config module."""
    return _get_settings()


def get_metrics():
    """Get metrics instance - imported from metrics module."""
    return _metrics


# Metrics will be imported when needed in _record_exception_metrics


def _record_exception_metrics(
    exception: Exception, component: str, component_type: Optional[str] = None
) -> None:
    """
    Record standardized exception metrics for any component

    COMPLEX LOGIC EXPLANATION:
    This function centralizes metrics recording for all exception types across the application.
    It handles different exception types with appropriate metrics:

    1. RATE LIMITS: Record rate limit hits with model information
    2. AUTH ERRORS: Record authentication failures
    3. CONNECTION ERRORS: Record network/connection issues
    4. UNEXPECTED ERRORS: Record any other exceptions

    The metrics are used for:
    - Monitoring system health
    - Identifying patterns in failures
    - Alerting on critical issues
    - Performance analysis

    Args:
        exception: The exception that occurred
        component: Component type ("guardrail" or "service")
        component_type: Specific component type for guardrails_total metric
    """
    try:
        settings = get_settings()
        metrics = get_metrics()

        model = settings.openai_model

        if component_type:
            # Record component error
            metrics.guardrails_total.labels(
                guardrail_type=component_type, result="error"
            ).inc()

        # Record specific error types
        if isinstance(exception, RateLimitError):
            metrics.openai_rate_limits_total.labels(
                model=model, limit_type="requests"
            ).inc()
            metrics.request_error_total.labels(
                component=component, error_type="rate_limit"
            ).inc()
        elif isinstance(exception, AuthenticationError):
            metrics.request_error_total.labels(
                component=component, error_type="authentication"
            ).inc()
        elif isinstance(exception, APITimeoutError):
            metrics.request_error_total.labels(
                component=component, error_type="timeout"
            ).inc()
        elif isinstance(exception, APIConnectionError):
            metrics.request_error_total.labels(
                component=component, error_type="connection"
            ).inc()
        else:
            metrics.request_error_total.labels(
                component=component, error_type="unexpected"
            ).inc()
    except ImportError:
        # Metrics not available, continue without them
        pass


class OpenAIExceptionHandler:
    """Centralized exception handling for OpenAI API calls"""

    @staticmethod
    def handle_openai_exceptions(
        success_callback: Callable[[], Any],
        rate_limit_callback: Optional[Callable[[Exception], Any]] = None,
        auth_error_callback: Optional[Callable[[Exception], Any]] = None,
        timeout_callback: Optional[Callable[[Exception], Any]] = None,
        connection_error_callback: Optional[Callable[[Exception], Any]] = None,
        generic_error_callback: Optional[Callable[[Exception], Any]] = None,
        log_prefix: str = "OpenAI API call",
    ) -> Any:
        """
        Handle OpenAI exceptions with customizable callbacks

        Args:
            success_callback: Function to call on successful API call
            rate_limit_callback: Function to call on RateLimitError
            auth_error_callback: Function to call on AuthenticationError
            timeout_callback: Function to call on APITimeoutError
            connection_error_callback: Function to call on APIConnectionError
            generic_error_callback: Function to call on other exceptions
            log_prefix: Prefix for log messages

        Returns:
            Result from the appropriate callback function
        """
        try:
            return success_callback()
        except RateLimitError as e:
            logger.warning(f"{log_prefix} - Rate limit exceeded: {str(e)}")
            if rate_limit_callback:
                return rate_limit_callback(e)
            raise
        except AuthenticationError as e:
            logger.error(f"{log_prefix} - Authentication error: {str(e)}")
            if auth_error_callback:
                return auth_error_callback(e)
            raise
        except APITimeoutError as e:
            logger.warning(f"{log_prefix} - API timeout: {str(e)}")
            if timeout_callback:
                return timeout_callback(e)
            raise
        except APIConnectionError as e:
            logger.warning(f"{log_prefix} - Connection error: {str(e)}")
            if connection_error_callback:
                return connection_error_callback(e)
            raise
        except Exception as e:
            logger.error(f"{log_prefix} - Unexpected error: {str(e)}", exc_info=True)
            if generic_error_callback:
                return generic_error_callback(e)
            raise


def openai_exception_handler(
    rate_limit_callback: Optional[Callable[[Exception], Any]] = None,
    auth_error_callback: Optional[Callable[[Exception], Any]] = None,
    timeout_callback: Optional[Callable[[Exception], Any]] = None,
    connection_error_callback: Optional[Callable[[Exception], Any]] = None,
    generic_error_callback: Optional[Callable[[Exception], Any]] = None,
    log_prefix: str = "OpenAI API call",
):
    """
    Decorator for handling OpenAI exceptions in functions

    Usage:
        @openai_exception_handler(
            rate_limit_callback=lambda e: {"error": "Rate limit exceeded"},
            log_prefix="Workflow analysis"
        )
        async def analyze_workflow(self, description: str):
            # Your OpenAI API call here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            def success_callback():
                return func(*args, **kwargs)

            return OpenAIExceptionHandler.handle_openai_exceptions(
                success_callback=success_callback,
                rate_limit_callback=rate_limit_callback,
                auth_error_callback=auth_error_callback,
                timeout_callback=timeout_callback,
                connection_error_callback=connection_error_callback,
                generic_error_callback=generic_error_callback,
                log_prefix=log_prefix,
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            def success_callback():
                return func(*args, **kwargs)

            return OpenAIExceptionHandler.handle_openai_exceptions(
                success_callback=success_callback,
                rate_limit_callback=rate_limit_callback,
                auth_error_callback=auth_error_callback,
                timeout_callback=timeout_callback,
                connection_error_callback=connection_error_callback,
                generic_error_callback=generic_error_callback,
                log_prefix=log_prefix,
            )

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class GuardrailExceptionHandler:
    """Specialized exception handler for guardrails"""

    @staticmethod
    def create_guardrail_error_response(
        output_type: Type, reasoning: str, tripwire: bool = True
    ) -> Dict[str, Any]:
        """Create standardized error response for guardrails"""
        # Create error response based on output type
        if output_type.__name__ == "NoteQueryDetectionOutput":
            return {
                "output_info": output_type(
                    is_note_query=False if tripwire else True,
                    reasoning=reasoning,
                ),
                "tripwire_triggered": tripwire,
            }
        elif output_type.__name__ == "JudgeNoteAnswerOutput":
            return {
                "output_info": output_type(
                    score="fail" if tripwire else "pass",
                    reasoning=reasoning,
                    tripwire_triggered=tripwire,
                ),
                "tripwire_triggered": tripwire,
            }
        else:
            # Generic fallback - try to create with minimal parameters
            try:
                return {
                    "output_info": output_type(reasoning=reasoning),
                    "tripwire_triggered": tripwire,
                }
            except Exception:
                # Ultimate fallback
                return {
                    "output_info": {"reasoning": reasoning},
                    "tripwire_triggered": tripwire,
                }

    @staticmethod
    def handle_guardrail_exception(
        exception: Exception,
        output_type: Type,
        log_prefix: str = "Guardrail",
        guardrail_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle a single exception for guardrails with standardized responses

        Args:
            exception: The exception that occurred
            output_type: Type of output object to create for errors
            log_prefix: Prefix for log messages
            guardrail_type: Type of guardrail for metrics (optional)

        Returns:
            Standardized error response
        """
        # Record standardized exception metrics
        _record_exception_metrics(
            exception=exception, component="guardrail", component_type=guardrail_type
        )
        if isinstance(exception, RateLimitError):
            logger.warning(f"{log_prefix} - Rate limit exceeded: {str(exception)}")
            return GuardrailExceptionHandler.create_guardrail_error_response(
                output_type,
                "Rate limit exceeded. Please try again later.",
                tripwire=True,
            )
        elif isinstance(exception, AuthenticationError):
            logger.error(f"{log_prefix} - Authentication error: {str(exception)}")
            return GuardrailExceptionHandler.create_guardrail_error_response(
                output_type,
                "API authentication error. Please contact support.",
                tripwire=True,
            )
        elif isinstance(exception, (APITimeoutError, APIConnectionError)):
            logger.warning(f"{log_prefix} - Connection/timeout error: {str(exception)}")
            return GuardrailExceptionHandler.create_guardrail_error_response(
                output_type,
                "Service temporarily unavailable. Please try again later.",
                tripwire=True,
            )
        else:
            logger.error(
                f"{log_prefix} - Unexpected error: {str(exception)}", exc_info=True
            )
            return GuardrailExceptionHandler.create_guardrail_error_response(
                output_type,
                "Guardrail error - allowing request to proceed",
                tripwire=False,
            )


class ServiceExceptionHandler:
    """Specialized exception handler for services"""

    @staticmethod
    def create_service_error_response(
        response_type: Type, reasoning: str, guardrails_tripped: list
    ) -> Any:
        """Create standardized error response for services"""
        # Try to create with query_answered=False for note queries
        try:
            return response_type(
                answer="An error occurred while processing your query.",
                reasoning=reasoning,
                relevant_files=[],
                original_query="",
                query_answered=False,
                guardrails_tripped=guardrails_tripped,
            )
        except Exception:
            # Fallback for other response types
            try:
                return response_type(
                    reasoning=reasoning,
                    guardrails_tripped=guardrails_tripped,
                )
            except Exception:
                # Ultimate fallback
                return {
                    "reasoning": reasoning,
                    "guardrails_tripped": guardrails_tripped,
                }

    @staticmethod
    def handle_service_exception(
        exception: Exception,
        response_type: Type,
        log_prefix: str = "Service",
        service_type: Optional[str] = None,
    ) -> Any:
        """
        Handle a single exception for services with standardized responses

        Args:
            exception: The exception that occurred
            response_type: Type of response object to create for errors
            log_prefix: Prefix for log messages
            service_type: Type of service for metrics (optional)

        Returns:
            Standardized error response
        """
        # Record standardized exception metrics
        _record_exception_metrics(
            exception=exception, component="service", component_type=service_type
        )
        if isinstance(exception, RateLimitError):
            logger.warning(f"{log_prefix} - Rate limit exceeded: {str(exception)}")
            return ServiceExceptionHandler.create_service_error_response(
                response_type,
                "Service temporarily unavailable due to rate limits. Please try again later.",
                ["rate_limit_exceeded"],
            )
        elif isinstance(exception, AuthenticationError):
            logger.error(f"{log_prefix} - Authentication error: {str(exception)}")
            return ServiceExceptionHandler.create_service_error_response(
                response_type,
                "Service configuration error. Please contact support.",
                ["authentication_error"],
            )
        elif isinstance(exception, APITimeoutError):
            logger.warning(f"{log_prefix} - API timeout: {str(exception)}")
            return ServiceExceptionHandler.create_service_error_response(
                response_type,
                "Service timeout. Please try again with a shorter description.",
                ["timeout"],
            )
        elif isinstance(exception, APIConnectionError):
            logger.warning(f"{log_prefix} - Connection error: {str(exception)}")
            return ServiceExceptionHandler.create_service_error_response(
                response_type,
                "Service temporarily unavailable. Please try again later.",
                ["connection_error"],
            )
        else:
            logger.error(
                f"{log_prefix} - Unexpected error: {str(exception)}", exc_info=True
            )
            return ServiceExceptionHandler.create_service_error_response(
                response_type, f"Error in service: {str(exception)}", ["analysis_error"]
            )
