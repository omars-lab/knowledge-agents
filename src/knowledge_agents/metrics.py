"""Prometheus metrics for the Agentic API."""

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest


class Metrics:
    """Container for all Prometheus metrics."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Clear any existing metrics to avoid duplication
        try:
            # Get all collectors and unregister them
            collectors = list(REGISTRY._collector_to_names.keys())
            for collector in collectors:
                REGISTRY.unregister(collector)
        except BaseException:
            pass
        # Database metrics
        self.db_connections_total = Counter(
            "database_connections_total", "Total database connections", ["status"]
        )
        self.db_connection_duration = Histogram(
            "database_connection_duration_seconds", "Database connection duration"
        )

        # Service metrics
        self.service_starts_total = Counter(
            "service_starts_total", "Total service starts"
        )

        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
        )

        # Workflow Analysis metrics
        self.workflow_analysis_total = Counter(
            "workflow_analysis_total",
            "Total workflow analysis requests",
            ["status", "model"],
        )
        self.workflow_analysis_duration = Histogram(
            "workflow_analysis_duration_seconds",
            "Workflow analysis processing duration",
            ["model"],
        )
        self.workflow_analysis_input_tokens = Histogram(
            "workflow_analysis_input_tokens",
            "Number of input tokens in workflow analysis",
            ["model"],
        )
        self.workflow_analysis_output_tokens = Histogram(
            "workflow_analysis_output_tokens",
            "Number of output tokens in workflow analysis",
            ["model"],
        )
        self.workflow_analysis_cost_usd = Histogram(
            "workflow_analysis_cost_usd", "Cost in USD for workflow analysis", ["model"]
        )
        self.workflow_analysis_apps_found = Histogram(
            "workflow_analysis_apps_found", "Number of apps found in workflow analysis"
        )
        self.workflow_analysis_actions_found = Histogram(
            "workflow_analysis_actions_found",
            "Number of actions found in workflow analysis",
        )

        # Guardrails metrics
        self.guardrails_total = Counter(
            "guardrails_total",
            "Total guardrail checks performed",
            ["guardrail_type", "result"],
        )
        self.guardrails_trip_total = Counter(
            "guardrails_trip_total", "Total guardrail trips by type", ["guardrail_type"]
        )
        self.guardrails_tripped_per_request = Histogram(
            "guardrails_tripped_per_request",
            "Number of guardrails tripped per request",
            buckets=[0, 1, 2, 3, 4, 5, 10, float("inf")],
        )
        self.guardrails_tripped_total = Counter(
            "guardrails_tripped_total", "Total number of guardrails tripped"
        )
        self.guardrails_processing_duration = Histogram(
            "guardrails_processing_duration_seconds",
            "Guardrail processing duration",
            ["guardrail_type"],
        )

        # Judge agent metrics
        self.judge_evaluations_total = Counter(
            "judge_evaluations_total",
            "Total judge evaluations performed",
            ["evaluation_type", "score"],
        )
        self.judge_score_distribution = Counter(
            "judge_score_distribution", "Distribution of judge scores", ["score"]
        )
        self.judge_processing_duration = Histogram(
            "judge_processing_duration_seconds",
            "Judge processing duration",
            ["evaluation_type"],
        )
        self.judge_accuracy_total = Counter(
            "judge_accuracy_total", "Total judge accuracy events", ["evaluation_type"]
        )

        # Quality metrics
        self.quality_score_distribution = Counter(
            "quality_score_distribution",
            "Distribution of quality scores",
            ["score", "component"],
        )
        self.quality_improvement_total = Counter(
            "quality_improvement_total",
            "Total quality improvement events",
            ["component"],
        )
        self.workflow_quality_score = Histogram(
            "workflow_quality_score",
            "Workflow quality score from judge output",
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # Business Critical Metrics
        self.guardrail_success_total = Counter(
            "guardrail_success_total",
            "Total number of requests that pass all guardrails",
            ["guardrail_type"],
        )
        self.guardrail_failure_total = Counter(
            "guardrail_failure_total",
            "Total number of requests that fail guardrails",
            ["guardrail_type"],
        )
        self.workflow_detection_total = Counter(
            "workflow_detection_total",
            "Total number of workflow detection events",
            ["detection_status"],
        )

        # OpenAI API Usage Metrics
        self.openai_api_calls_total = Counter(
            "openai_api_calls_total",
            "Total OpenAI API calls made",
            ["model", "endpoint", "status"],
        )
        self.openai_api_duration = Histogram(
            "openai_api_duration_seconds",
            "OpenAI API call duration",
            ["model", "endpoint"],
        )
        self.openai_tokens_used = Counter(
            "openai_tokens_used_total",
            "Total OpenAI tokens used",
            ["model", "token_type"],
        )
        self.openai_cost_total = Counter(
            "openai_cost_total_usd", "Total OpenAI API cost in USD", ["model"]
        )
        self.openai_rate_limits_total = Counter(
            "openai_rate_limits_total",
            "Total OpenAI rate limit hits",
            ["model", "limit_type"],
        )

        # Request Success Metrics
        self.request_success_total = Counter(
            "request_success_total",
            "Total successful requests",
            ["endpoint", "status_code"],
        )
        self.request_error_total = Counter(
            "request_error_total", "Total failed requests", ["component", "error_type"]
        )
        self.end_to_end_duration = Histogram(
            "end_to_end_duration_seconds",
            "End-to-end request processing duration",
            ["endpoint"],
        )

        # AI Agent Performance Metrics
        self.ai_agent_consistency = Histogram(
            "ai_agent_consistency_score",
            "AI agent response consistency score",
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        self.ai_agent_quality_score = Histogram(
            "ai_agent_quality_score",
            "AI agent quality assessment score",
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        self.ai_agent_processing_time = Histogram(
            "ai_agent_processing_time_seconds",
            "AI agent processing time",
            ["agent_type"],
        )

        # System Health Metrics
        self.system_health_score = Histogram(
            "system_health_score",
            "Overall system health score",
            buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        self.concurrent_requests = Histogram(
            "concurrent_requests", "Number of concurrent requests being processed"
        )
        self.memory_usage_bytes = Histogram(
            "memory_usage_bytes", "Memory usage in bytes"
        )

    def generate_metrics(self) -> str:
        """Generate Prometheus metrics output."""
        # Ensure all metrics are initialized by calling them once
        self.db_connections_total.labels(status="success")
        self.db_connections_total.labels(status="error")

        # Force metric registration by incrementing
        self.db_connections_total.labels(status="success").inc(0)
        self.db_connections_total.labels(status="error").inc(0)
        self.db_connection_duration.observe(0.0)

        # Initialize all new metrics to ensure they appear in output
        # Business Critical Metrics
        self.guardrail_success_total.labels(guardrail_type="ai_analysis").inc(0)
        self.guardrail_failure_total.labels(guardrail_type="ai_analysis").inc(0)
        self.workflow_detection_total.labels(detection_status="detected").inc(0)
        self.workflow_detection_total.labels(detection_status="none").inc(0)
        self.guardrails_tripped_per_request.observe(0.0)
        self.guardrails_tripped_total.inc(0)

        # OpenAI API Usage Metrics
        self.openai_api_calls_total.labels(
            model="gpt-3.5-turbo", endpoint="chat/completions", status="success"
        ).inc(0)
        self.openai_api_duration.labels(
            model="gpt-3.5-turbo", endpoint="chat/completions"
        ).observe(0.0)
        self.openai_tokens_used.labels(model="gpt-3.5-turbo", token_type="input").inc(0)
        self.openai_cost_total.labels(model="gpt-3.5-turbo").inc(0)
        self.openai_rate_limits_total.labels(
            model="gpt-3.5-turbo", limit_type="requests"
        ).inc(0)

        # Request Success Metrics
        self.request_success_total.labels(
            endpoint="/api/v1/analyze", status_code="200"
        ).inc(0)
        self.request_error_total.labels(component="api", error_type="validation").inc(0)
        self.end_to_end_duration.labels(endpoint="/api/v1/analyze").observe(0.0)

        # AI Agent Performance Metrics
        self.ai_agent_consistency.observe(0.0)
        self.ai_agent_quality_score.observe(0.0)
        self.ai_agent_processing_time.labels(agent_type="workflow").observe(0.0)

        # System Health Metrics
        self.system_health_score.observe(0.0)
        self.concurrent_requests.observe(0.0)
        self.memory_usage_bytes.observe(0.0)

        return generate_latest().decode("utf-8")


# Global metrics instance
metrics = Metrics()
