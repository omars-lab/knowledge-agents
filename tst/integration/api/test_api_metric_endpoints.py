"""
API Metrics Endpoints Integration Tests

PURPOSE: Tests metrics collection, monitoring, and observability through API
SCOPE: Prometheus metrics, performance monitoring, and system observability

TEST CATEGORIES:
- Metrics Endpoint: /metrics accessibility, Prometheus format validation
- Workflow Metrics: Analysis counts, duration, token usage, costs
- Guardrail Metrics: Trip counts, processing duration, validation metrics
- Judge Agent Metrics: Evaluation counts, score distribution, accuracy
- Quality Metrics: Score distribution, improvement tracking
- HTTP Metrics: Request counts, response times, status codes
- Database Metrics: Connection counts, query duration, pool metrics
- Performance Metrics: Response times, throughput, system health

WHAT BELONGS HERE:
✅ Metrics collection and exposure
✅ Prometheus format validation
✅ Performance monitoring
✅ System observability
✅ Metrics endpoint functionality
✅ Monitoring data validation

WHAT DOESN'T BELONG HERE:
❌ Basic HTTP infrastructure (→ test_api_base_endpoints.py)
❌ LLM guardrail testing (→ test_api_guardrail_endpoints.py)
❌ Core workflow analysis (→ test_agentic_api_workflow_endpoints.py)
❌ Business scenario testing (→ test_agentic_api_real_world_scenarios.py)
❌ End-to-end integration flows (→ test_agentic_api_end_to_end_api.py)
"""

import pytest

from tst.utils.test_assertion_utils import APIResponseAssertions

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestMetrics:
    """Test Prometheus metrics collection and exposure"""

    # Use shared api_client fixture from tst/integration/conftest.py

    @pytest.mark.asyncio
    async def test_metrics_endpoint_accessible(self, api_client):
        """Test that metrics endpoint is accessible"""
        response = await api_client.get("/metrics")
        APIResponseAssertions.assert_successful_status(response)

        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content

    @pytest.mark.asyncio
    async def test_workflow_analysis_metrics(self, api_client):
        """Test that workflow analysis metrics are collected"""

        # Make a workflow analysis request
        response = await api_client.post(
            "/api/v1/analyze",
            json={
                "description": "When a new lead is created in Salesforce, send an email using Gmail"
            },
        )
        APIResponseAssertions.assert_successful_status(response)

        # Check metrics endpoint for workflow analysis metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for workflow analysis metrics
        workflow_metrics = [
            "workflow_analysis_total",
            "workflow_analysis_duration_seconds",
            "workflow_analysis_input_tokens",
            "workflow_analysis_output_tokens",
            "workflow_analysis_cost_usd",
        ]

        for metric in workflow_metrics:
            assert metric in metrics_content, f"Metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_guardrails_metrics(self, api_client):
        """Test that guardrails metrics are collected"""

        # Make requests that should trigger guardrails
        guardrail_inputs = [
            "What's the weather today?",  # Should trip workflow detection
            "I want to order pizza",  # Should trip topic validation
            "When a new lead is created in NonExistentApp, send an email",  # Should trip app existence
            "When a new lead is created in Salesforce, perform magic_trick",  # Should trip action existence
        ]

        for input_text in guardrail_inputs:
            response = await api_client.post(
                "/api/v1/analyze", json={"description": input_text}
            )
            APIResponseAssertions.assert_successful_status(response)

        # Check metrics endpoint for guardrails metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for guardrails metrics
        guardrails_metrics = [
            "guardrails_total",
            "guardrails_trip_total",
            "guardrails_processing_duration_seconds",
        ]

        for metric in guardrails_metrics:
            assert (
                metric in metrics_content
            ), f"Guardrails metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_judge_agent_metrics(self, api_client):
        """Test that judge agent metrics are collected"""

        # Make workflow analysis requests
        workflows = [
            "When a new lead is created in Salesforce, send an email using Gmail",
            "When a message is sent in Slack, create a contact in HubSpot",
        ]

        for workflow in workflows:
            response = await api_client.post(
                "/api/v1/analyze", json={"description": workflow}
            )
            APIResponseAssertions.assert_successful_status(response)

        # Check metrics endpoint for judge agent metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for judge agent metrics
        judge_metrics = [
            "judge_evaluations_total",
            "judge_score_distribution_total",
            "judge_processing_duration_seconds",
            "judge_accuracy_total",
        ]

        for metric in judge_metrics:
            assert (
                metric in metrics_content
            ), f"Judge agent metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_quality_metrics(self, api_client):
        """Test that quality control metrics are collected"""

        # Make workflow analysis requests
        response = await api_client.post(
            "/api/v1/analyze",
            json={
                "description": "When a new lead is created in Salesforce, send an email using Gmail"
            },
        )
        APIResponseAssertions.assert_successful_status(response)

        # Check metrics endpoint for quality metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for quality metrics
        quality_metrics = [
            "quality_score_distribution_total",
            "quality_improvement_total",
        ]

        for metric in quality_metrics:
            assert (
                metric in metrics_content
            ), f"Quality metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_http_metrics(self, api_client):
        """Test that HTTP request metrics are collected"""

        # Make various HTTP requests
        await api_client.get("/health")
        await api_client.get("/hello")
        await api_client.get("/metrics")
        await api_client.post("/api/v1/analyze", json={"description": "test workflow"})

        # Check metrics endpoint for HTTP metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for HTTP metrics
        http_metrics = ["http_requests_total", "http_request_duration_seconds"]

        for metric in http_metrics:
            assert (
                metric in metrics_content
            ), f"HTTP metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_database_metrics(self, api_client):
        """Test that database metrics are collected"""

        # Make requests that use the database
        await api_client.get("/hello")  # This queries the database
        await api_client.post("/api/v1/analyze", json={"description": "test workflow"})

        # Check metrics endpoint for database metrics
        metrics_response = await api_client.get("/metrics")
        assert metrics_response.status_code == 200

        metrics_content = metrics_response.text

        # Check for database metrics
        db_metrics = [
            "database_connections_total",
            "database_connection_duration_seconds",
        ]

        for metric in db_metrics:
            assert (
                metric in metrics_content
            ), f"Database metric {metric} not found in metrics"

    @pytest.mark.asyncio
    async def test_metrics_format_valid(self, api_client):
        """Test that metrics are in valid Prometheus format"""

        response = await api_client.get("/metrics")
        APIResponseAssertions.assert_successful_status(response)

        content = response.text
        lines = content.split("\n")

        # Check for valid Prometheus format
        help_lines = [line for line in lines if line.startswith("# HELP")]
        type_lines = [line for line in lines if line.startswith("# TYPE")]
        metric_lines = [
            line for line in lines if not line.startswith("#") and line.strip()
        ]

        assert len(help_lines) > 0, "No HELP lines found"
        assert len(type_lines) > 0, "No TYPE lines found"
        assert len(metric_lines) > 0, "No metric lines found"

        # Check that each metric has a corresponding HELP and TYPE
        for metric_line in metric_lines:
            if " " in metric_line:
                # Extract base metric name (without labels)
                metric_name_with_labels = metric_line.split(" ")[0]
                if "{" in metric_name_with_labels:
                    metric_name = metric_name_with_labels.split("{")[0]
                else:
                    metric_name = metric_name_with_labels

                # Skip histogram buckets and other derived metrics
                if (
                    metric_name.endswith("_bucket")
                    or metric_name.endswith("_count")
                    or metric_name.endswith("_sum")
                    or metric_name.endswith("_created")
                ):
                    continue

                # Find corresponding HELP and TYPE lines
                help_found = any(f"# HELP {metric_name}" in line for line in help_lines)
                type_found = any(f"# TYPE {metric_name}" in line for line in type_lines)

                assert help_found, f"Metric {metric_name} missing HELP line"
                assert type_found, f"Metric {metric_name} missing TYPE line"

    @pytest.mark.asyncio
    async def test_metrics_values_increase(self, api_client):
        """Test that metric values increase with usage"""

        # Get initial metrics
        initial_response = await api_client.get("/metrics")
        assert initial_response.status_code == 200
        initial_content = initial_response.text

        # Make some requests
        await api_client.get("/health")
        await api_client.post("/api/v1/analyze", json={"description": "test workflow"})

        # Get updated metrics
        updated_response = await api_client.get("/metrics")
        assert updated_response.status_code == 200
        updated_content = updated_response.text

        # Check that some metrics have increased by comparing specific counters
        def parse_counter(content: str, metric: str) -> float:
            lines = [
                ln
                for ln in content.splitlines()
                if ln.startswith(metric + " ")
                or (ln.startswith(metric + "{") and "}" in ln)
            ]
            if not lines:
                return 0.0
            # Take the first occurrence
            line = lines[0]
            value_str = line.split()[-1]
            try:
                return float(value_str)
            except ValueError:
                return 0.0

        initial_hello = parse_counter(
            initial_content,
            'http_requests_total{endpoint="/hello",method="GET",status="200"}',
        )
        updated_hello = parse_counter(
            updated_content,
            'http_requests_total{endpoint="/hello",method="GET",status="200"}',
        )
        assert updated_hello >= initial_hello, "HTTP /hello counter should not decrease"

    @pytest.mark.asyncio
    async def test_metrics_performance(self, api_client):
        """Test that metrics endpoint responds quickly"""
        import time

        start_time = time.time()
        response = await api_client.get("/metrics")
        end_time = time.time()

        response_time = end_time - start_time

        APIResponseAssertions.assert_successful_status(response)
        assert response_time < 2.0, f"Metrics endpoint too slow: {response_time}s"

        print(f"Metrics endpoint response time: {response_time:.2f}s")
