"""Explicit real-provider integration-test placeholder.

This test remains skipped until an approved Google Street View provider adapter
and authorized project configuration are supplied. Normal tests never contact
Google.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_REAL_STREETVIEW_INTEGRATION") != "1",
    reason="Real authorized Street View integration is disabled.",
)
def test_real_authorized_streetview_metadata_discovery():
    pytest.skip("Authorized Street View access is not configured.")