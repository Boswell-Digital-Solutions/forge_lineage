"""Pytest configuration that exposes the SDK without requiring `pip install`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SDK_PATH = Path(__file__).resolve().parent.parent / "sdk"
if str(_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(_SDK_PATH))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--dataforge-local",
        default=os.environ.get("DATAFORGE_LOCAL"),
        help="path to a dataforge-Local checkout for integration tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a compatible dataforge-Local checkout",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip explicitly marked cross-repository tests unless their service is available."""
    configured_path = config.getoption("dataforge_local")
    default_path = Path(__file__).resolve().parents[3] / "dataforge-Local"
    dataforge_local = Path(configured_path) if configured_path else default_path

    if dataforge_local.is_dir():
        if str(dataforge_local) not in sys.path:
            sys.path.insert(0, str(dataforge_local))
        return

    reason = (
        "requires dataforge-Local; pass --dataforge-local PATH or set "
        "DATAFORGE_LOCAL"
    )
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip)
