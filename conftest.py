"""Pytest configuration: track gated tests so we can fail silent-green CI."""
import os
import pytest

GATED_RAN: list = []


@pytest.fixture(autouse=True)
def _maybe_record_gated(request):
    """If a test was annotated `pytest.mark.gated_real`, record that it ran."""
    if request.node.get_closest_marker("gated_real"):
        GATED_RAN.append(request.node.nodeid)
    yield


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gated_real: marks tests that hit the real n8n instance (skip if N8N_API_KEY unset)",
    )
