"""Tests for ISO external folder browsing functionality."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from gui.iso_manager import ISOManager, EXTERNAL_ISO_CONFIG


@pytest.fixture
def tmp_iso_env(tmp_path, monkeypatch):
    """Set up a temporary ISO environment with internal + external dirs."""
    internal_dir = tmp_path / "iso"
    internal_dir.mkdir()

    ext_dir = tmp_path / "external"
    ext_dir.mkdir()

    # Create test ISO files
    (internal_dir / "internal.iso").write_bytes(b"x" * 1024)
    (internal_dir / "internal.img").write_bytes(b"y" * 2048)
    (ext_dir / "external.iso").write_bytes(b"z" * 4096)
    sub_dir = ext_dir / "subfolder"
    sub_dir.mkdir()
    (sub_dir / "nested.img").write_bytes(b"w" * 512)

    # Patch paths
    monkeypatch.setattr("gui.iso_manager.INTERNAL_ISO_DIR", internal_dir)
    monkeypatch.setattr("gui.iso_manager.EXTERNAL_ISO_CONFIG", tmp_path / ".iso-sources.json")

    return {"internal": internal_dir, "external": ext_dir, "tmp": tmp_path}


class TestExternalISOScanning:
    """Tests for external ISO scanning functionality."""

    def test_scan_finds_img_and_iso(self, tmp_iso_env):
        """Scan should find both .img and .iso files."""
        mgr = ISOManager()
        mgr.add_external_source(tmp_iso_env["external"])
        isos = mgr.scan_external_isos()
        names = {iso["name"] for iso in isos}
        assert "external" in names
        assert "nested" in names

    def test_scan_isos_includes_internal_and_external(self, tmp_iso_env):
        """scan_isos should include both internal and external."""
        mgr = ISOManager()
        mgr.add_external_source(tmp_iso_env["external"])
        isos = mgr.scan_isos()
        names = {iso["name"] for iso in isos}
        assert "internal" in names
        assert "external" in names
        assert "nested" in names

    def test_scan_returns_correct_columns(self, tmp_iso_env):
        """Each ISO entry should have name, size, size_human, source, path, modified."""
        mgr = ISOManager()
        mgr.add_external_source(tmp_iso_env["external"])
        isos = mgr.scan_external_isos()
        assert len(isos) >= 1
        iso = isos[0]
        assert "name" in iso
        assert "size" in iso
        assert "size_human" in iso
        assert "source" in iso
        assert "path" in iso
        assert "modified" in iso
        assert iso["source"] == "external"

    def test_add_and_remove_source(self, tmp_iso_env):
        """Adding and removing sources should work correctly."""
        mgr = ISOManager()
        src = tmp_iso_env["external"]

        # Add
        assert mgr.add_external_source(src) is True
        assert src.resolve() in mgr.get_external_sources()

        # Remove
        assert mgr.remove_external_source(src) is True
        assert src.resolve() not in mgr.get_external_sources()

        # Remove non-existent
        assert mgr.remove_external_source("/nonexistent/path") is False

    def test_remove_from_list_widget_source(self, tmp_iso_env):
        """Removing a source should also remove its ISOs from scan results."""
        mgr = ISOManager()
        src = tmp_iso_env["external"]
        mgr.add_external_source(src)

        # Should find external ISOs
        isos = mgr.scan_external_isos()
        assert len(isos) >= 1

        # After removal
        mgr.remove_external_source(src)
        isos = mgr.scan_external_isos()
        assert len(isos) == 0

    def test_external_sources_persist_to_json(self, tmp_iso_env):
        """External sources should be saved to .iso-sources.json."""
        mgr = ISOManager()
        src = tmp_iso_env["external"]
        mgr.add_external_source(src)

        config_file = tmp_iso_env["tmp"] / ".iso-sources.json"
        assert config_file.exists()

        with open(config_file) as f:
            data = json.load(f)
        assert "sources" in data
        assert str(src.resolve()) in data["sources"]

    def test_load_sources_from_json(self, tmp_iso_env):
        """Sources should be loaded from .iso-sources.json on init."""
        # Write a config file directly
        config_file = tmp_iso_env["tmp"] / ".iso-sources.json"
        config_file.write_text(json.dumps({"sources": [str(tmp_iso_env["external"].resolve())]}))

        mgr = ISOManager()
        assert tmp_iso_env["external"].resolve() in mgr.get_external_sources()

    def test_format_timestamp(self, tmp_iso_env):
        """format_timestamp should return a formatted date string."""
        result = ISOManager.format_timestamp(1700000000.0)
        assert isinstance(result, str)
        assert "2023" in result  # Approximate check

    def test_scan_nonexistent_source(self, tmp_iso_env):
        """Scanning with a nonexistent source should return empty list."""
        mgr = ISOManager()
        mgr.add_external_source("/nonexistent/path/that/doesnt/exist")
        isos = mgr.scan_external_isos()
        assert isos == []
