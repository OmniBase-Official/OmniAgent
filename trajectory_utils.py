"""Shared parsing helpers for exported and validated trajectories."""

from __future__ import annotations


def actions_in(reply: str) -> list[str]:
    """Extract action names from model replies while preserving encounter order."""
    return [
        line.strip().split(":", 1)[1].strip()
        for line in reply.splitlines()
        if line.strip().lower().startswith("action:")
    ]
