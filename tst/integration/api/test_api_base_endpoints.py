"""
API Base Endpoints Integration Tests

PURPOSE: Tests basic API infrastructure, HTTP behavior, and input validation
SCOPE: Core API functionality that doesn't require business logic or LLM processing

TEST CATEGORIES:
- Health & Status Endpoints: /health, /hello, /, /metrics
- HTTP Infrastructure: Headers, status codes, content types
- Basic API Contract: Endpoint existence, method support
- Error Handling: 405 method not allowed

WHAT BELONGS HERE:
✅ Basic HTTP endpoint functionality
✅ Response headers and content types
✅ Basic error handling (405 method not allowed)

WHAT DOESN'T BELONG HERE:
❌ Input validation for /api/v1/analyze (→ test_agentic_api_endpoint.py)
❌ LLM guardrail testing (→ test_agentic_api_guardrails.py)
❌ Workflow analysis business logic (→ test_agentic_api_workflow_endpoints.py)
❌ Metrics collection testing (→ test_api_metric_endpoints.py)
❌ Business scenario testing (→ test_agentic_api_real_world_scenarios.py)
❌ End-to-end integration flows (→ test_agentic_api_end_to_end_api.py)
"""
import asyncio

import pytest

from tst.utils.test_assertion_utils import (
    APIResponseAssertions,
    HTTPStatusAssertions,
    JSONStructureAssertions,
    SecurityAssertions,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestAPIEndpoints:
    """Test API endpoint functionality"""

    # Use shared api_client fixture from tst/integration/conftest.py

    async def test_health_endpoint(self, api_client):
        """Test health check endpoint"""
        response = await api_client.get("/health")

        APIResponseAssertions.assert_successful_status(response)
        data = response.json()
        JSONStructureAssertions.assert_health_check_structure(data)

    async def test_hello_endpoint(self, api_client):
        """Test hello endpoint with canary monitoring"""
        response = await api_client.get("/hello")

        APIResponseAssertions.assert_successful_status(response)
        data = response.json()
        JSONStructureAssertions.assert_hello_endpoint_structure(data)

    async def test_metrics_endpoint(self, api_client):
        """Test metrics endpoint returns Prometheus format"""
        response = await api_client.get("/metrics")

        APIResponseAssertions.assert_successful_status(response)
        content = response.text
        JSONStructureAssertions.assert_metrics_content_structure(content)

    async def test_root_endpoint(self, api_client):
        """Test root endpoint returns service info"""
        response = await api_client.get("/")

        APIResponseAssertions.assert_successful_status(response)
        data = response.json()
        JSONStructureAssertions.assert_service_info_structure(data)

    async def test_error_handling(self, api_client):
        """Test API error handling"""
        # Test unsupported method
        response = await api_client.put("/api/v1/analyze", json={"description": "test"})
        HTTPStatusAssertions.assert_method_not_allowed(response)

    async def test_response_headers(self, api_client):
        """Test response headers are properly set"""
        response = await api_client.get("/health")

        APIResponseAssertions.assert_successful_status(response)
        assert "content-type" in response.headers
        assert "application/json" in response.headers["content-type"]
