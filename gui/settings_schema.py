"""Settings schema migration system.

Provides a versioned settings store with a migration chain so that
future config changes don't break existing installs.  Each migration
is a pure function that transforms a settings dict from one version
to the next.

Usage:
    from gui.settings_schema import load_settings, save_settings

    data = load_settings("gui/settings.json")
    data["new_key"] = "value"
    save_settings(data, "gui/settings.json")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


# ── Schema version ─────────────────────────────────────────────────────────────

_schema_version: int = 1


# ── Migration chain ────────────────────────────────────────────────────────────

_migrations: list[tuple[int, Callable[[dict[str, Any]], dict[str, Any]]]] = []


def _migration(to_version: int) -> Callable:
    """Decorator to register a migration function.

    The decorated function receives a dict and must return the
    transformed dict.  Migrations are run in order of target version.
    """

    def decorator(fn: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable:
        _migrations.append((to_version, fn))
        return fn

    return decorator


@_migration(1)
def _migrate_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Initial schema version — baseline, no structural changes.

    This migration exists as an anchor so future migrations have a
    clear starting point.  It ensures the ``_schema_version`` key
    is present and set to 1.
    """
    return data


# ── Public API ────────────────────────────────────────────────────────────────


def migrate_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Run all pending migrations on the settings dict.

    Checks ``_schema_version`` on the input dict.  If the key is
    missing or less than the current ``_schema_version``, runs each
    migration function in sequence until the dict is up to date.

    Args:
        data: The settings dict to migrate.

    Returns:
        The migrated dict with ``_schema_version`` set to the current
        schema version.
    """
    current: int = data.get("_schema_version", 0)

    if current >= _schema_version:
        return data

    # Sort migrations by target version to ensure correct order
    for to_ver, fn in sorted(_migrations, key=lambda x: x[0]):
        if current < to_ver:
            data = fn(data)
            current = to_ver

    data["_schema_version"] = _schema_version
    return data


def load_settings(path: str | Path) -> dict[str, Any]:
    """Load settings from a JSON file, running migrations.

    If the file does not exist, returns a fresh dict with only
    ``_schema_version`` set to the current schema version.

    Args:
        path: Path to the JSON settings file.

    Returns:
        The loaded (and migrated) settings dict.
    """
    p = Path(path)

    if not p.exists():
        return {"_schema_version": _schema_version}

    with open(p, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    return migrate_settings(data)


def save_settings(data: dict[str, Any], path: str | Path) -> None:
    """Save settings to a JSON file with the current schema version.

    Sets ``_schema_version`` on the dict before writing so that
    future loads can detect the schema version.

    Args:
        data: The settings dict to save.
        path: Path to the JSON settings file.
    """
    data["_schema_version"] = _schema_version

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")