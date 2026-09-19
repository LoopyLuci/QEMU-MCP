"""Tests for vm-mcp configuration and core functionality."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Config tests ────────────────────────────────────────────────────────────────

class TestVmMCPSettings:
    """Tests for VmMCPSettings configuration."""

    def test_default_settings(self):
        """Default settings should have sensible values."""
        from vm_mcp.config import VmMCPSettings

        settings = VmMCPSettings()
        assert settings.server_name == "vm-mcp"
        assert settings.server_version == "0.1.0"
        assert settings.transport == "stdio"
        assert settings.log_level == "INFO"
        assert settings.vm_name == "omarchy-vm"
        assert settings.vm_ram_mb == 8192
        assert settings.vm_cpus == 4
        assert settings.ssh_port == 2222  # QEMU user-mode NAT forwarding port
        assert settings.ssh_username == "OmarchyVM"

    def test_qmp_uri_tcp(self, monkeypatch):
        """QMP URI should be tcp:host:port when no socket path."""
        from vm_mcp.config import VmMCPSettings

        settings = VmMCPSettings()
        assert settings.qmp_uri() == "tcp:127.0.0.1:4444"

    def test_qmp_uri_unix(self, monkeypatch):
        """QMP URI should be unix:path when socket path is set."""
        from vm_mcp.config import VmMCPSettings

        settings = VmMCPSettings(qmp_socket_path="/tmp/qmp.sock")
        assert settings.qmp_uri() == "unix:/tmp/qmp.sock"

    def test_path_expansion(self, monkeypatch):
        """Paths with ~ and $vars should be expanded."""
        from vm_mcp.config import VmMCPSettings

        monkeypatch.setenv("TEST_DISK", "/custom/path/disk.qcow2")
        settings = VmMCPSettings(vm_disk_path="$TEST_DISK")
        assert settings.vm_disk_path == "/custom/path/disk.qcow2"


class TestSecrets:
    """Tests for Secrets management."""

    def test_empty_secrets(self):
        """Empty secrets should mask to empty."""
        from vm_mcp.config import Secrets

        s = Secrets()
        assert s.mask() == "Secrets()"
        assert not s.has_ssh_creds()
        assert not s.has_any_secret()

    def test_from_env(self, monkeypatch):
        """Secrets should load from environment variables."""
        from vm_mcp.config import Secrets

        monkeypatch.setenv("SSH_PASSWORD", "testpass")
        monkeypatch.setenv("AUTH_API_KEY", "testkey")
        s = Secrets.from_env()
        assert s.get_ssh_password() == "testpass"
        assert s.get_auth_api_key() == "testkey"
        assert s.has_ssh_creds()
        assert s.has_any_secret()
        assert "ssh_password=***" in s.mask()
        assert "auth_api_key=***" in s.mask()

    def test_from_dotenv(self, tmp_path):
        """Secrets should load from a .env file."""
        from vm_mcp.config import Secrets

        env_file = tmp_path / ".env"
        env_file.write_text(
            "SSH_PASSWORD=dotenvpass\n"
            "AUTH_API_KEY=dotenvkey\n"
        )
        s = Secrets.from_dotenv(str(env_file))
        assert s.get_ssh_password() == "dotenvpass"
        assert s.get_auth_api_key() == "dotenvkey"

    def test_mask_does_not_expose_secrets(self, monkeypatch):
        """Masked secrets must never contain raw values."""
        from vm_mcp.config import Secrets

        monkeypatch.setenv("SSH_PASSWORD", "SuperSecret123!")
        monkeypatch.setenv("AUTH_API_KEY", "sk-test-abc123")
        s = Secrets.from_env()
        masked = s.mask()
        assert "SuperSecret123" not in masked
        assert "sk-test-abc123" not in masked
        assert "***" in masked


# ── Tool parameter validation (schema tests) ────────────────────────────────────

class TestToolSchemas:
    """Tests for tool input schema validation."""

    def test_vm_status_schema(self):
        """vm_status tool should be a Tool instance with correct metadata."""
        from vm_mcp.tools.vm_lifecycle import vm_status_fn
        from vm_mcp.tools.base import Tool

        # vm_status_fn is wrapped by @tool() — it's a Tool instance
        assert isinstance(vm_status_fn, Tool)
        assert vm_status_fn.meta.name == "vm_status"

    def test_guest_exec_requires_command(self):
        """guest_exec must have 'command' as a required parameter."""
        schema = {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 30},
                "env": {"type": "object"},
            },
            "required": ["command"],
        }
        assert "command" in schema["required"]
        assert schema["properties"]["command"]["type"] == "string"

    def test_guest_file_read_requires_path(self):
        """guest_file_read must have 'path' as a required parameter."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 1048576},
            },
            "required": ["path"],
        }
        assert "path" in schema["required"]


# ── SSH client tests (unit, no actual connection) ──────────────────────────────

class TestSSHClientUnit:
    """Unit tests for SSH client helper functions (no real connection)."""

    def test_build_qemu_args_count(self):
        """build_qemu_args should produce a non-empty list."""
        from vm_mcp.setup import build_qemu_args
        from vm_mcp.config import VmMCPSettings

        settings = VmMCPSettings()
        args = build_qemu_args(settings)
        assert len(args) > 10  # QEMU has many arguments
        assert args[0] == settings.qemu_binary  # First arg is the binary

    def test_build_qemu_args_with_iso(self):
        """build_qemu_args with start_iso=True should include CDROM args."""
        from vm_mcp.setup import build_qemu_args
        from vm_mcp.config import VmMCPSettings

        settings = VmMCPSettings()
        settings.vm_iso_path = r"C:\test\omarchy.iso"
        args = build_qemu_args(settings, start_iso=True)
        assert "-drive" in args
        assert "cdrom" in " ".join(args)
        assert "-boot" in args

    def test_qmp_client_initialization(self):
        """QMPClient should store URI and connection state."""
        from vm_mcp.qmp_client import QMPClient

        client = QMPClient("tcp:127.0.0.1:4444")
        assert client.uri == "tcp:127.0.0.1:4444"
        assert not client.is_connected

    def test_qmp_client_unix_uri(self):
        """QMPClient should accept unix: URIs."""
        from vm_mcp.qmp_client import QMPClient

        client = QMPClient("unix:/tmp/qmp.sock")
        assert client.uri == "unix:/tmp/qmp.sock"


# ── Skills tests ────────────────────────────────────────────────────────────────

class TestSkills:
    """Tests for the skills system."""

    def test_skill_count(self):
        """Should have at least 3 skills defined."""
        from vm_mcp.skills import SKILLS
        assert len(SKILLS) >= 3

    def test_skill_names(self):
        """Skill names should be unique and non-empty."""
        from vm_mcp.skills import SKILLS
        names = [s.name for s in SKILLS]
        assert len(names) == len(set(names))  # No duplicates
        assert all(name for name in names)

    def test_get_skill(self):
        """get_skill should return the correct skill."""
        from vm_mcp.skills import get_skill

        skill = get_skill("vm_lifecycle")
        assert skill is not None
        assert skill.name == "vm_lifecycle"
        assert len(skill.tools) > 0

    def test_get_unknown_skill(self):
        """get_skill should return None for unknown names."""
        from vm_mcp.skills import get_skill
        assert get_skill("nonexistent_skill") is None

    def test_list_skills(self):
        """list_skills should return all skills."""
        from vm_mcp.skills import list_skills
        skills = list_skills()
        assert len(skills) >= 3
