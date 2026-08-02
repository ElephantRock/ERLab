"""Shared fixtures for API tests.

Ensures the database is initialized before any API test runs.
This fixes the 'no such table' errors on CI where the DB path
may differ from the development environment.
"""
import pytest
from backend.db.database import init_db


@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Initialize the database once for all API tests."""
    init_db()
