"""
Integration agents client configuration fixture.

This fixture ensures the agents framework has a default OpenAI client configured.
It uses test dependencies when available, falling back to direct client creation.
"""
import logging

import pytest
from agents import set_default_openai_client

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True, scope="function")
@pytest.mark.fixtures_integration
def configure_agents_client(inject_test_api_key):
    """Ensure the agents framework has a default OpenAI client for all tests.

    This fixture uses the test dependencies (initialized by inject_test_api_key)
    to configure the default OpenAI client for the agents framework.
    """
    try:
        # Try to get dependencies - if available, use them
        from knowledge_agents.dependencies import get_dependencies

        deps = get_dependencies()
        client = deps.openai_client
        set_default_openai_client(client)
        logger.debug("Configured agents framework client from test dependencies")
    except RuntimeError:
        # Dependencies not initialized - this is OK for some tests
        logger.debug(
            "Dependencies not initialized, skipping agents client configuration"
        )
    except Exception as e:
        # Non-fatal: some tests don't hit the agent codepaths
        logger.debug(f"Non-fatal error configuring agents client: {e}")
