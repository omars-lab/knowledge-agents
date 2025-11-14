"""
Top-level pytest configuration applied to all tests (unit and integration).

This module is imported by both unit and integration tests, but doesn't
automatically configure agents client anymore. Instead, use the
test_dependencies fixture or inject_test_api_key fixture from
tst/integration/fixtures/litellm_api_key.py for integration tests.
"""
