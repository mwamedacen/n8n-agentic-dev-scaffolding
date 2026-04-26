"""Fail silent-green CI: when N8N_API_KEY is set, ≥1 gated test must run."""
import os

import pytest

import conftest


def test_gated_tests_ran_when_api_key_present():
    if not os.environ.get("N8N_API_KEY"):
        pytest.skip("N8N_API_KEY unset; gated tests intentionally skipped")
    assert conftest.GATED_RAN, (
        "N8N_API_KEY is set but no gated tests ran — silent-green protection. "
        "Make sure tests are annotated `@pytest.mark.gated_real`."
    )
