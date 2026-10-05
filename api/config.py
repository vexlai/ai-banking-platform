"""Runtime configuration helpers for the API gateway.

`USE_MOCKS` is the process-wide default, but each request may override it with
an explicit parameter, so the resolution logic lives here rather than in
`main.py` (which would create an import cycle with the routes).
"""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, *, default: bool) -> bool:
    """Reads a boolean environment flag; unknown values fall back to `default`."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def use_mocks_default() -> bool:
    """Process default for mock serving, read dynamically so tests can patch it."""
    return env_flag("USE_MOCKS", default=True)


def resolve_use_mocks(value: bool | None) -> bool:
    """A request parameter wins when present; otherwise the environment decides."""
    return value if value is not None else use_mocks_default()
