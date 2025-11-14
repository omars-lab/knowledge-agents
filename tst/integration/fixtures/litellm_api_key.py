"""
Fixture for generating LiteLLM API keys for integration tests.

This fixture ensures that tests have a valid API key without relying on
external secrets. It generates a key via the LiteLLM proxy and makes it
available to test settings.
"""
import logging
import os
import time

import httpx
import pytest

logger = logging.getLogger(__name__)

# Test API key cache - stores generated key per test session
_TEST_API_KEY = None
_TEST_API_KEY_GENERATED_AT = None


@pytest.fixture(scope="session")
def litellm_api_key():
    """
    Generate or retrieve a LiteLLM API key for integration tests.

    This fixture:
    1. Generates a new API key via the LiteLLM proxy
    2. Caches it for the test session
    3. Returns the key for use in test settings

    The key is generated with access to all test models:
    - lm_studio/qwen3-coder-30b
    - qwen3-coder-30b
    - lm_studio/gpt-oss-20b
    - lm_studio/text-embedding-qwen3-embedding-8b
    """
    global _TEST_API_KEY, _TEST_API_KEY_GENERATED_AT

    # Return cached key if it exists and is recent (within last hour)
    if _TEST_API_KEY and _TEST_API_KEY_GENERATED_AT:
        age_seconds = time.time() - _TEST_API_KEY_GENERATED_AT
        if age_seconds < 3600:  # 1 hour
            logger.info(f"Using cached test API key (age: {age_seconds:.0f}s)")
            return _TEST_API_KEY

    # Generate new API key
    logger.info("Generating new LiteLLM API key for tests...")

    master_key = "sk-1234"
    # In Docker, use service name; locally, use localhost
    proxy_host = os.getenv("LITELLM_PROXY_HOST", "llm-proxy")
    proxy_port = os.getenv("LITELLM_PROXY_PORT", "4000")
    proxy_url = f"http://{proxy_host}:{proxy_port}"

    # Wait for proxy to be ready with better error handling
    max_retries = 60  # Increased timeout for slower environments
    for i in range(max_retries):
        try:
            response = httpx.get(f"{proxy_url}/health", timeout=5.0)
            if response.status_code in [200, 401]:  # 401 is OK for health check
                logger.info(f"✅ LiteLLM proxy is ready (attempt {i+1}/{max_retries})")
                break
        except httpx.ConnectError:
            if i < max_retries - 1:
                logger.debug(f"Waiting for LiteLLM proxy... (attempt {i+1}/{max_retries})")
            else:
                pytest.fail(
                    f"LiteLLM proxy not reachable at {proxy_url}. "
                    f"Make sure the proxy service is running and healthy."
                )
        except Exception as e:
            if i < max_retries - 1:
                logger.debug(f"Error checking proxy health: {e}")
            else:
                pytest.fail(f"Error checking LiteLLM proxy health: {e}")
        
        if i < max_retries - 1:
            time.sleep(1)
        else:
            pytest.fail(
                f"LiteLLM proxy not ready after {max_retries} attempts. "
                f"Check proxy logs: docker compose logs llm-proxy"
            )

    # Wait a bit more for database to be ready (LiteLLM needs DB for key storage)
    logger.debug("Waiting for LiteLLM database to be ready...")
    time.sleep(3)

    # Generate API key
    models = [
        "lm_studio/qwen3-coder-30b",
        "qwen3-coder-30b",
        "lm_studio/gpt-oss-20b",
        "lm_studio/text-embedding-qwen3-embedding-8b",
    ]

    try:
        response = httpx.post(
            f"{proxy_url}/key/generate",
            headers={
                "Authorization": f"Bearer {master_key}",
                "Content-Type": "application/json",
            },
            json={
                "models": models,
                "metadata": {
                    "user": "test@integration.test",
                    "purpose": "integration_test",
                },
            },
            timeout=10.0,
        )

        if response.status_code not in [200, 201]:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except Exception:
                pass
            
            pytest.fail(
                f"Failed to generate API key: HTTP {response.status_code}. "
                f"Error: {error_detail}. "
                f"Check LiteLLM proxy logs and ensure master key is correct."
            )

        # Extract key from response
        data = response.json()
        api_key = data.get("key") or data.get("api_key")

        if not api_key:
            pytest.fail(f"API key not found in response: {data}")

        # Cache the key
        _TEST_API_KEY = api_key
        _TEST_API_KEY_GENERATED_AT = time.time()

        logger.info(f"✅ Generated test API key (first 16 chars: {api_key[:16]}...)")
        return api_key

    except Exception as e:
        pytest.fail(f"Error generating API key: {e}")


@pytest.fixture(scope="function")
def test_dependencies(litellm_api_key):
    """
    Create test Dependencies instance with injected API key.

    This fixture provides a Dependencies container with test settings,
    allowing tests to use explicit dependency injection instead of
    global state or monkey-patching.
    """
    from knowledge_agents.config.api_config import Settings
    from knowledge_agents.dependencies import Dependencies, reset_dependencies

    # Reset global dependencies to ensure clean state
    reset_dependencies()

    # Create test settings with API key override and test collection name
    test_settings = Settings(
        openai_api_key=litellm_api_key,
        environment="test",
        qdrant_collection_name="test_noteplan_files_collection",  # Use test collection
    )

    # Create test dependencies
    test_deps = Dependencies(settings=test_settings)
    logger.debug(
        f"Created test Dependencies with API key (first 10 chars: {litellm_api_key[:10]}...)"
    )

    yield test_deps

    # Cleanup
    reset_dependencies()


@pytest.fixture(scope="function", autouse=True)
def inject_test_api_key(litellm_api_key):
    """
    Automatically initialize global dependencies with test API key.

    This ensures backward compatibility for code that still uses
    get_dependencies() instead of explicit dependency injection.
    For new code, prefer using the test_dependencies fixture.
    """
    from knowledge_agents.config.api_config import Settings
    from knowledge_agents.dependencies import (
        initialize_dependencies,
        reset_dependencies,
    )

    # Reset global dependencies
    reset_dependencies()

    # Create test settings with API key override and test collection name
    test_settings = Settings(
        openai_api_key=litellm_api_key,
        environment="test",
        qdrant_collection_name="test_noteplan_files_collection",  # Use test collection
    )

    # Initialize global dependencies (for backward compatibility)
    initialize_dependencies(test_settings)
    logger.debug(
        f"Initialized global dependencies with test API key (first 10 chars: {litellm_api_key[:10]}...)"
    )

    yield

    # Cleanup
    reset_dependencies()
