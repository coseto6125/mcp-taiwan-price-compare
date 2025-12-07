"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_query() -> str:
    """Sample search query for testing."""
    return "iPhone 15"


@pytest.fixture
def sample_query_cheap() -> str:
    """Sample search query for cheap items."""
    return "手機殼"
