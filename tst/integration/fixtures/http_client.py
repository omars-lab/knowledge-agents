"""
Integration HTTP client and service-wait fixtures.
"""
import asyncio
import os

import httpx
import pytest


@pytest.fixture(scope="session")
@pytest.mark.fixtures_integration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    try:
        yield loop
    finally:
        # Explicitly close to avoid DeprecationWarning about unclosed loop
        loop.close()


@pytest.fixture
@pytest.mark.fixtures_integration
def api_client(litellm_api_key):
    """
    FastAPI async test client for integration tests with API token in headers.
    
    Uses 'agentic-api' service hostname and includes Authorization header.
    """
    base_url = os.getenv("API_BASE_URL", "http://agentic-api:8000")
    # Include Authorization header with API token
    headers = {"Authorization": f"Bearer {litellm_api_key}"}
    return httpx.AsyncClient(base_url=base_url, timeout=60.0, headers=headers)


@pytest.fixture(scope="session")
@pytest.mark.fixtures_integration
async def wait_for_services():
    """
    Wait for all services to be healthy before running tests.
    
    This fixture ensures:
    1. API service is running and healthy
    2. All dependent services (postgres, qdrant, llm-proxy, tidy-mcp) are ready
    3. Proper error messages if services fail to start
    """
    import time
    import logging

    logger = logging.getLogger(__name__)
    
    # Use agentic-api service hostname
    base_url = os.getenv("API_BASE_URL", "http://agentic-api:8000")
    
    # Wait for services to be ready
    max_wait = 180  # seconds
    start_time = time.time()
    last_error = None

    while time.time() - start_time < max_wait:
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
                response = await client.get("/health")
                if response.status_code == 200:
                    logger.info(f"✅ Services are healthy (connected via {base_url})")
                    return
        except httpx.ConnectError as e:
            last_error = f"Connection error to {base_url}: {e}"
        except httpx.TimeoutException as e:
            last_error = f"Timeout connecting to {base_url}: {e}"
        except Exception as e:
            last_error = f"Unexpected error connecting to {base_url}: {e}"

        await asyncio.sleep(2)
    
    # If we get here, services didn't become healthy
    error_msg = (
        f"Services did not become healthy within {max_wait}s timeout. "
        f"Last error: {last_error}. "
        f"Make sure to run 'make test-note-query-prepare' first."
    )
    logger.error(error_msg)
    pytest.fail(error_msg)


@pytest.fixture
@pytest.mark.fixtures_integration
def tidy_mcp_url():
    """Get tidy-mcp service URL from environment"""
    return os.getenv("TIDY_MCP_URL", "http://tidy-mcp:8000")


@pytest.fixture
@pytest.mark.fixtures_integration
def tidy_mcp_available(tidy_mcp_url):
    """Check if tidy-mcp service is available and healthy"""
    import requests
    
    try:
        response = requests.get(f"{tidy_mcp_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
