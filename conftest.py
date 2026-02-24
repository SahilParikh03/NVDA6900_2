"""
Root conftest for the NVDA Earnings War Room test suite.

Sets required environment variables BEFORE any backend module is imported,
so that ``backend.config.Settings`` can instantiate without raising a
``ValidationError`` for the missing ``FMP_API_KEY``.
"""

import os

# Must be set before any import of backend.config triggers Settings()
os.environ.setdefault("FMP_API_KEY", "test-key-not-real")
