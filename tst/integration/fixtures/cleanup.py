"""
Integration test cleanup fixtures.
"""
import pytest

from .integ_test_data import clear_all_data


@pytest.fixture(autouse=True)
@pytest.mark.fixtures_integration
async def cleanup_db():
    """Clean database before each test and seed it with fresh data."""
    await clear_all_data()
    # Seed the database with fresh data after cleanup
    from .integ_test_data import seed_comprehensive_noteplan_data

    await seed_comprehensive_noteplan_data()
    yield
    await clear_all_data()
