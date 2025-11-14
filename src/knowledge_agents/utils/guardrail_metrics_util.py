"""
Shared utilities for guardrail logging and metrics recording
"""
import logging
import time
from typing import Any, Dict, Optional

from ..metrics import metrics

logger = logging.getLogger(__name__)


class GuardrailMetrics:
    """Utility class for recording guardrail metrics and logging"""

    def __init__(self, guardrail_type: str, log_prefix: str):
        self.guardrail_type = guardrail_type
        self.log_prefix = log_prefix
        self.start_time = time.time()

    def record_success(self, result: str = "passed") -> None:
        """Record successful guardrail execution"""
        duration = time.time() - self.start_time
        metrics.guardrails_processing_duration.labels(
            guardrail_type=self.guardrail_type
        ).observe(duration)
        metrics.guardrails_total.labels(
            guardrail_type=self.guardrail_type, result=result
        ).inc()
        metrics.guardrail_success_total.labels(guardrail_type=self.guardrail_type).inc()
        logger.info(f"{self.log_prefix}: Guardrail PASSED - {result}")

    def record_failure(self, result: str = "failed") -> None:
        """Record failed guardrail execution"""
        duration = time.time() - self.start_time
        metrics.guardrails_processing_duration.labels(
            guardrail_type=self.guardrail_type
        ).observe(duration)
        metrics.guardrails_total.labels(
            guardrail_type=self.guardrail_type, result=result
        ).inc()
        metrics.guardrail_failure_total.labels(guardrail_type=self.guardrail_type).inc()
        logger.warning(f"{self.log_prefix}: Guardrail FAILED - {result}")

    def record_error(self, exception: Exception) -> None:
        """Record guardrail error"""
        duration = time.time() - self.start_time
        metrics.guardrails_processing_duration.labels(
            guardrail_type=self.guardrail_type
        ).observe(duration)
        metrics.guardrails_total.labels(
            guardrail_type=self.guardrail_type, result="error"
        ).inc()
        logger.error(
            f"{self.log_prefix}: Exception occurred: {str(exception)}", exc_info=True
        )

    def log_result(self, result_data: Dict[str, Any], tripwire_triggered: bool) -> None:
        """Log guardrail result with structured data"""
        result_str = "FAILED" if tripwire_triggered else "PASSED"
        logger.info(
            f"{self.log_prefix}: Result - {result_data}, tripwire_triggered={tripwire_triggered}"
        )
        logger.info(f"{self.log_prefix}: Guardrail {result_str}")

    def log_start(self) -> None:
        """Log guardrail start"""
        logger.info(f"{self.log_prefix}: Starting guardrail check")

    def log_agent_run(self) -> None:
        """Log agent run start"""
        logger.info(f"{self.log_prefix}: Running guardrail agent")

    def log_agent_complete(self) -> None:
        """Log agent run completion"""
        logger.info(f"{self.log_prefix}: Agent run completed successfully")


def record_guardrail_metrics(
    guardrail_type: str,
    log_prefix: str,
    tripwire_triggered: bool,
    start_time: Optional[float] = None,
    result_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    One-liner utility to record guardrail metrics and logging

    Args:
        guardrail_type: Type of guardrail for metrics
        log_prefix: Prefix for log messages
        tripwire_triggered: Whether the guardrail was triggered
        start_time: Start time for duration calculation (optional)
        result_data: Additional result data to log (optional)
    """
    metrics_recorder = GuardrailMetrics(guardrail_type, log_prefix)

    if start_time:
        metrics_recorder.start_time = start_time

    if result_data:
        metrics_recorder.log_result(result_data, tripwire_triggered)

    if tripwire_triggered:
        metrics_recorder.record_failure()
    else:
        metrics_recorder.record_success()
