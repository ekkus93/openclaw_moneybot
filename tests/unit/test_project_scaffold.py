"""Tests for the initial project scaffold."""

from __future__ import annotations

import sys

import openclaw_moneybot


def test_python_version_is_311() -> None:
    """The project targets Python 3.11 and allows newer review interpreters."""
    assert sys.version_info[:2] >= (3, 11)


def test_package_version() -> None:
    """The package exposes a version."""
    assert openclaw_moneybot.__version__ == "0.1.0"
