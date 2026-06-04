"""Shared utilities for IT Support Analytics Hub."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def format_percent(value: float) -> str:
    """Format a decimal value as a percentage string."""
    return f"{float(value or 0):.1%}"


def format_hours(value: float) -> str:
    """Format hours with one decimal place."""
    return f"{float(value or 0):,.1f}h"


def format_number(value: float) -> str:
    """Format a number without unnecessary decimals."""
    return f"{float(value or 0):,.0f}"

