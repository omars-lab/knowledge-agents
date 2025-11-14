"""
Test improvements and utilities for better test reliability and organization.
"""
import asyncio
import logging
import time
from typing import Any, Callable, Optional

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
@pytest.mark.fixtures_integration
def log_test_start(request):
    """Log test start and end for better debugging."""
    test_name = request.node.name
    logger.info(f"🧪 Starting test: {test_name}")
    start_time = time.time()
    
    yield
    
    duration = time.time() - start_time
    logger.info(f"✅ Completed test: {test_name} (duration: {duration:.2f}s)")


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
    backoff: float = 1.5,
):
    """
    Decorator to retry test functions on failure.
    
    Useful for flaky tests that might fail due to timing or external dependencies.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        exceptions: Tuple of exceptions to catch and retry on
        backoff: Multiplier for delay after each retry
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Test {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay:.2f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Test {func.__name__} failed after {max_retries} attempts")
                        raise
        
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Test {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay:.2f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Test {func.__name__} failed after {max_retries} attempts")
                        raise
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@pytest.fixture
def skip_if_service_unavailable():
    """
    Fixture that provides a helper to skip tests if a service is unavailable.
    
    Usage:
        def test_something(skip_if_service_unavailable):
            skip_if_service_unavailable("llm-proxy", "http://llm-proxy:4000/health")
    """
    async def _skip_if_unavailable(service_name: str, health_url: str):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(health_url)
                if response.status_code not in [200, 401]:
                    pytest.skip(f"Service {service_name} is not available (status: {response.status_code})")
        except Exception as e:
            pytest.skip(f"Service {service_name} is not available: {e}")
    
    return _skip_if_unavailable

