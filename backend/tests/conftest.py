# backend/tests/conftest.py
"""
Root conftest for all backend tests. Ensures sqlite-specific OPTIONS
stripping runs before ANY test is collected.
"""

from tests.signals.conftest import pytest_configure  # noqa: F401
