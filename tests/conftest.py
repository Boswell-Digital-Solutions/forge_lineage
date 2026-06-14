"""Pytest configuration that exposes the SDK without requiring `pip install`."""

from __future__ import annotations

import sys
from pathlib import Path

_SDK_PATH = Path(__file__).resolve().parent.parent / "sdk"
if str(_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(_SDK_PATH))
