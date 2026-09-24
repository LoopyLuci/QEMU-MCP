"""Tests for the settings schema migration system."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gui.settings_schema import (
    _schema_version as SCHEMA_VERSION,
    load_settings,
    migrate_settings,
    save_settings,
)


class TestSettingsMigration(unittest.TestCase):
    """Test cases for settings migration logic."""

    def test_migrate_old_settings(self):
        """Old-format settings (no _schema_version) get migrated."""
        old_settings = {
            "theme": "dark",
            "default_ram_mb": 2048,
            "default_disk_size_gb": 40,
            "network_mode": "bridge",
        }

        migrated = migrate_settings(old_settings)

        self.assertEqual(migrated["_schema_version"], SCHEMA_VERSION)
        # Preserve existing keys
        self.assertEqual(migrated["theme"], "dark")
        self.assertEqual(migrated["default_ram_mb"], 2048)

    def test_migrate_current_settings_unchanged(self):
        """Current settings dict is returned unchanged (except no-op version check)."""
        current_settings = {
            "_schema_version": SCHEMA_VERSION,
            "theme": "light",
            "default_ram_mb": 4096,
        }

        migrated = migrate_settings(current_settings)

        self.assertEqual(migrated["_schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["theme"], "light")
        self.assertEqual(migrated["default_ram_mb"], 4096)

    def test_migrate_returns_same_object_when_current(self):
        """migrate_settings returns the same dict object when already current."""
        current_settings = {"_schema_version": SCHEMA_VERSION, "key": "value"}

        migrated = migrate_settings(current_settings)

        self.assertIs(migrated, current_settings)

    def test_save_and_load_roundtrip(self):
        """Save then load preserves all settings."""
        settings = {
            "theme": "dark",
            "default_ram_mb": 2048,
            "default_disk_size_gb": 80,
            "network_mode": "nat",
            "theme_custom": "#ff5500",
            "auto_start_vms": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_settings.json"

            save_settings(settings, path)
            loaded = load_settings(path)

            # All original keys preserved
            for key, value in settings.items():
                self.assertEqual(loaded[key], value, f"Key '{key}' not preserved")

            # Schema version set correctly
            self.assertEqual(loaded["_schema_version"], SCHEMA_VERSION)

    def test_save_load_roundtrip_empty_settings(self):
        """Save then load an empty dict results in just _schema_version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_settings.json"

            save_settings({}, path)
            loaded = load_settings(path)

            self.assertEqual(loaded["_schema_version"], SCHEMA_VERSION)
            self.assertEqual(len(loaded), 1)

    def test_load_nonexistent_file(self):
        """Loading a non-existent file returns default settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent" / "settings.json"

            loaded = load_settings(path)

            self.assertEqual(loaded, {"_schema_version": SCHEMA_VERSION})

    def test_save_sets_schema_version(self):
        """save_settings sets _schema_version on the saved dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_settings.json"

            data = {"theme": "dark"}
            save_settings(data, path)

            # The in-place dict should also have _schema_version
            self.assertEqual(data["_schema_version"], SCHEMA_VERSION)

            # And the file content
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["_schema_version"], SCHEMA_VERSION)

    def test_save_creates_parent_dirs(self):
        """save_settings creates missing parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "settings.json"

            save_settings({"key": "value"}, path)

            self.assertTrue(path.exists())

    def test_migrate_from_version_zero(self):
        """Dict with _schema_version=0 gets migrated to current."""
        old_data = {
            "_schema_version": 0,
            "key": "value",
        }

        migrated = migrate_settings(old_data)

        self.assertEqual(migrated["_schema_version"], SCHEMA_VERSION)
        self.assertEqual(migrated["key"], "value")


if __name__ == "__main__":
    unittest.main()
