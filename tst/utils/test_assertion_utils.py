"""
Common test utilities and assertion methods for integration tests
"""
from typing import Any, Dict, List, Optional


class WorkflowStepResponseAssertions:
    """Common assertion methods for workflow step analysis responses"""

    @staticmethod
    def assert_successful_response_structure(response_data: Dict[str, Any]) -> None:
        """Assert that response has the correct structure for successful workflow step analysis"""
        # Handle both old and new field names for backward compatibility
        workflow_detected_field = (
            "workflow_step_detected"
            if "workflow_step_detected" in response_data
            else "workflow_detected"
        )

        required_fields = [
            workflow_detected_field,
            "app",
            "action",
            "reasoning",
        ]

        for field in required_fields:
            assert (
                field in response_data
            ), f"Required field '{field}' missing from response"

        # Check data types are correct
        assert isinstance(
            response_data[workflow_detected_field], bool
        ), f"{workflow_detected_field} should be boolean"
        assert isinstance(
            response_data["app"], (str, type(None))
        ), "app should be string or null"
        assert isinstance(
            response_data["action"], (str, type(None))
        ), "action should be string or null"
        assert isinstance(response_data["reasoning"], str), "reasoning should be string"

        # Check reasoning is not empty
        assert len(response_data["reasoning"]) > 0, "reasoning should not be empty"

    @staticmethod
    def assert_successful_step_detected(
        response_data: Dict[str, Any],
        expected_app: Optional[str] = None,
        expected_action: Optional[str] = None,
    ) -> None:
        """Assert that a workflow step was successfully detected with optional app/action validation"""
        # Handle both old and new field names for backward compatibility
        workflow_detected_field = (
            "workflow_step_detected"
            if "workflow_step_detected" in response_data
            else "workflow_detected"
        )

        assert (
            response_data[workflow_detected_field] is True
        ), "Should detect valid workflow step"
        assert response_data["app"] is not None, "Should identify an app"
        assert response_data["action"] is not None, "Should identify an action"

        if expected_app:
            assert (
                response_data["app"] == expected_app
            ), f"Expected app '{expected_app}', got '{response_data['app']}'"

        if expected_action:
            assert (
                response_data["action"] == expected_action
            ), f"Expected action '{expected_action}', got '{response_data['action']}'"

    # Note: Removed multi-app/action assertion methods since the API is step-focused
    # and only returns single app and action per request

    @staticmethod
    def assert_app_fuzzy_match(
        response_data: Dict[str, Any], expected_app_pattern: str
    ) -> None:
        """Assert that an app matches a fuzzy pattern (case-insensitive, partial match)"""
        assert "app" in response_data, "Response should include app field"
        app = response_data["app"]
        assert app is not None, "App should not be None"
        assert (
            expected_app_pattern.lower() in app.lower()
        ), f"Expected app pattern '{expected_app_pattern}' not found in '{app}'"

    @staticmethod
    def assert_action_fuzzy_match(
        response_data: Dict[str, Any], expected_action_pattern: str
    ) -> None:
        """Assert that an action matches a fuzzy pattern (case-insensitive, partial match)"""
        assert "action" in response_data, "Response should include action field"
        action = response_data["action"]
        assert action is not None, "Action should not be None"
        assert (
            expected_action_pattern.lower() in action.lower()
        ), f"Expected action pattern '{expected_action_pattern}' not found in '{action}'"

    @staticmethod
    def assert_no_step_detected(response_data: Dict[str, Any]) -> None:
        """Assert that no valid workflow step was detected"""
        # Handle both old and new field names for backward compatibility
        workflow_detected = response_data.get(
            "workflow_step_detected", response_data.get("workflow_detected", True)
        )
        assert workflow_detected is False, "Should not detect workflow step"
        assert response_data["app"] is None, "Should not identify an app"
        assert response_data["action"] is None, "Should not identify an action"

    @staticmethod
    def assert_ambiguity_detected(response_data: Dict[str, Any]) -> None:
        """Assert that ambiguity was detected in the workflow step"""
        assert (
            "ambiguity_detected" in response_data
        ), "Response should include ambiguity_detected field"
        assert (
            response_data["ambiguity_detected"] is True
        ), "Should detect ambiguity in workflow step"

    @staticmethod
    def assert_guardrails_tripped(
        response_data: Dict[str, Any], expected_guardrails: Optional[List[str]] = None
    ) -> None:
        """Assert that specific guardrails were tripped"""
        assert (
            "guardrails_tripped" in response_data
        ), "Response should include guardrails_tripped field"

        if expected_guardrails:
            for guardrail in expected_guardrails:
                assert (
                    guardrail in response_data["guardrails_tripped"]
                ), f"Expected guardrail '{guardrail}' to be tripped"

    @staticmethod
    def assert_any_guardrails_tripped(
        response_data: Dict[str, Any], possible_guardrails: List[str]
    ) -> None:
        """
        Assert that any of the possible guardrails were tripped

        COMPLEX LOGIC EXPLANATION:
        This method handles the fact that input guardrails run in PARALLEL, not sequentially.
        This means multiple guardrails can trip simultaneously for the same input.

        For example, "Use MadeUpApp to send email" could trip:
        - MENTIONS_EXISTING_APP (because MadeUpApp doesn't exist)
        - MENTIONS_EXISTING_ACTION (because it can't validate actions for non-existent app)

        This flexible assertion allows tests to pass if ANY of the expected guardrails trip,
        rather than requiring a specific one to trip.
        """
        assert (
            "guardrails_tripped" in response_data
        ), "Response should include guardrails_tripped field"

        tripped_guardrails = response_data["guardrails_tripped"]
        assert len(tripped_guardrails) > 0, "At least one guardrail should be tripped"

        # Check if any of the possible guardrails are in the tripped list
        # This handles parallel guardrail execution where multiple can trip
        any_tripped = any(
            guardrail in tripped_guardrails for guardrail in possible_guardrails
        )
        assert (
            any_tripped
        ), f"Expected one of {possible_guardrails} to be tripped, but got {tripped_guardrails}"

    @staticmethod
    def assert_no_guardrails_tripped(response_data: Dict[str, Any]) -> None:
        """Assert that no guardrails were tripped"""
        assert (
            "guardrails_tripped" in response_data
        ), "Response should include guardrails_tripped field"
        assert (
            len(response_data["guardrails_tripped"]) == 0
        ), "No guardrails should be tripped"

    @staticmethod
    def assert_response_consistency(responses: List[Dict[str, Any]]) -> None:
        """Assert that multiple responses are consistent"""
        if len(responses) < 2:
            return

        for i in range(1, len(responses)):
            # Core workflow step detection should be consistent
            assert (
                responses[i]["workflow_step_detected"]
                == responses[0]["workflow_step_detected"]
            ), "Workflow step detection should be consistent across requests"

            # App and action should be consistent (allowing for AI variability)
            assert (
                responses[i]["app"] == responses[0]["app"]
            ), f"App should be consistent: {responses[i]['app']} vs {responses[0]['app']}"
            assert (
                responses[i]["action"] == responses[0]["action"]
            ), f"Action should be consistent: {responses[i]['action']} vs {responses[0]['action']}"


class APIResponseAssertions:
    """Common assertion methods for API responses"""

    @staticmethod
    def assert_successful_status(response) -> None:
        """Assert that response has successful status code"""
        assert (
            response.status_code == 200
        ), f"Expected 200 status code, got {response.status_code}"

    @staticmethod
    def assert_validation_error(response) -> None:
        """Assert that response indicates validation error"""
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 status code for validation error, got {response.status_code}"

    @staticmethod
    def assert_server_error(response) -> None:
        """Assert that response indicates server error"""
        assert response.status_code in [
            500,
            502,
            503,
        ], f"Expected 5xx status code for server error, got {response.status_code}"


class PerformanceAssertions:
    """Common assertion methods for performance testing"""

    @staticmethod
    def assert_response_time(
        response_time: float, max_seconds: float = 5.0, min_seconds: float = 0.1
    ) -> None:
        """Assert that response time is within acceptable bounds"""
        assert (
            response_time < max_seconds
        ), f"Response time {response_time:.2f}s exceeds {max_seconds}s threshold"
        assert (
            response_time > min_seconds
        ), f"Response time {response_time:.2f}s seems too fast (possible caching issue)"


class SecurityAssertions:
    """Common assertion methods for security testing"""

    @staticmethod
    def assert_no_malicious_content(
        response_data: Dict[str, Any], malicious_patterns: List[str]
    ) -> None:
        """Assert that response does not contain malicious content"""
        response_str = str(response_data)

        for pattern in malicious_patterns:
            assert (
                pattern not in response_str
            ), f"Response should not contain malicious pattern: {pattern}"

    @staticmethod
    def assert_input_sanitized(response_data: Dict[str, Any]) -> None:
        """Assert that input was properly sanitized"""
        malicious_patterns = [
            "<script>",
            "DROP TABLE",
            "{{7*7}}",
            "javascript:",
        ]

        SecurityAssertions.assert_no_malicious_content(
            response_data, malicious_patterns
        )


class JSONStructureAssertions:
    """Common assertion methods for JSON structure validation"""

    @staticmethod
    def assert_health_check_structure(data: Dict[str, Any]) -> None:
        """Assert that health check response has correct structure"""
        assert "status" in data, "Health check should include status field"
        assert "database" in data, "Health check should include database field"
        assert "timestamp" in data, "Health check should include timestamp field"
        assert data["status"] == "healthy", "Health status should be 'healthy'"

    @staticmethod
    def assert_hello_endpoint_structure(data: Dict[str, Any]) -> None:
        """Assert that hello endpoint response has correct structure"""
        assert "message" in data, "Hello endpoint should include message field"
        assert "timestamp" in data, "Hello endpoint should include timestamp field"

    @staticmethod
    def assert_service_info_structure(data: Dict[str, Any]) -> None:
        """Assert that service info response has correct structure"""
        assert "service" in data, "Service info should include service field"
        assert "version" in data, "Service info should include version field"

    @staticmethod
    def assert_metrics_content_structure(content: str) -> None:
        """Assert that metrics endpoint returns valid Prometheus format"""
        assert (
            "workflow_analysis_total" in content or "guardrails_total" in content
        ), "Metrics should contain workflow metrics"
        assert (
            "HELP" in content or "# TYPE" in content
        ), "Metrics should be in Prometheus format"


class HTTPStatusAssertions:
    """Common assertion methods for HTTP status codes"""

    @staticmethod
    def assert_success_or_validation_error(response) -> None:
        """Assert that response is either successful or validation error"""
        assert response.status_code in [
            200,
            422,
        ], f"Expected 200 or 422 status code, got {response.status_code}"

    @staticmethod
    def assert_method_not_allowed(response) -> None:
        """Assert that response indicates method not allowed"""
        assert (
            response.status_code == 405
        ), f"Expected 405 status code, got {response.status_code}"

    @staticmethod
    def assert_validation_error(response) -> None:
        """Assert that response indicates validation error"""
        assert (
            response.status_code == 422
        ), f"Expected 422 status code for validation error, got {response.status_code}"

    @staticmethod
    def assert_metrics_endpoint_success(response) -> None:
        """Assert that metrics endpoint returns successful response"""
        assert (
            response.status_code == 200
        ), f"Expected 200 status code for metrics, got {response.status_code}"
