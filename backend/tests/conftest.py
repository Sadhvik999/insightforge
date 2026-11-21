import os
import pytest


@pytest.fixture(autouse=True)
def default_allow_local_dev(monkeypatch):
    """
    During test suite execution, permit local dev endpoints (loopback) by default,
    unless explicitly overridden by a specific test via monkeypatch.setenv.
    In production environments without this flag, ALLOW_LOCAL_CUSTOM_API defaults to false.
    """
    if "ALLOW_LOCAL_CUSTOM_API" not in os.environ:
        monkeypatch.setenv("ALLOW_LOCAL_CUSTOM_API", "true")
