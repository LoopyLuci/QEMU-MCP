"""Skills package — agent-facing capability definitions.

Skills describe higher-level workflows that an agent can perform using
the MCP tools.  They are not MCP tools themselves but documentation
that helps agents understand what they can do and how to do it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    """A named skill that an agent can use.

    Skills combine related tools into a workflow with a description
    of what they do and how to use them.
    """

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    example: str = ""
    notes: str = ""


# ── Available Skills ────────────────────────────────────────────────────────────

SKILLS: list[Skill] = [
    Skill(
        name="vm_lifecycle",
        description=(
            "Manage the QEMU virtual machine lifecycle: start, stop, reset, "
            "suspend, resume, eject ISO, and configure boot order.  These "
            "tools use QMP (QEMU Machine Protocol) to control the VM directly."
        ),
        tools=["vm_status", "vm_start", "vm_stop", "vm_reset", "vm_suspend", "vm_resume", "vm_eject_cdrom", "vm_boot_device"],
        example=(
            "To install Omarchy: call vm_start with boot_iso=true, wait for "
            "installation to complete, then call vm_eject_cdrom and vm_reset."
        ),
        notes=(
            "vm_start with boot_iso=true boots from the installer ISO.  "
            "After installation, boot from disk (default).  vm_eject_cdrom "
            "should be called after install to remove the ISO."
        ),
    ),
    Skill(
        name="guest_interaction",
        description=(
            "Interact with the running Omarchy guest VM via SSH: execute "
            "commands, read/write files, list directories, and remove files. "
            "All operations run as the configured SSH user (OmarchyVM)."
        ),
        tools=["guest_exec", "guest_file_read", "guest_file_write", "guest_file_list", "guest_file_remove"],
        example=(
            "To check if Omarchy is installed: call guest_exec with command "
            "\"cat /etc/os-release\".  To create a file: call "
            "guest_file_write with path and content."
        ),
        notes=(
            "Commands are non-interactive only (no shell prompts).  Use "
            "command chaining (&&, ||) for complex workflows.  File paths "
            "are relative to the guest's root filesystem."
        ),
    ),
    Skill(
        name="vm_monitoring",
        description=(
            "Monitor the VM's health and status.  Use vm_status to check if "
            "the VM is running, paused, or stopped.  Combine with guest_exec "
            "to check guest-level metrics."
        ),
        tools=["vm_status", "guest_exec"],
        example=(
            "To monitor VM health: call vm_status to check VM state, then "
            "guest_exec with \"uptime && free -h\" to check guest resources."
        ),
    ),
    Skill(
        name="iso_management",
        description=(
            "Manage the installation ISO: boot from it for installation, "
            "eject it after install completes.  The ISO is at the path "
            "configured in the .env file."
        ),
        tools=["vm_start", "vm_eject_cdrom", "vm_boot_device"],
        example=(
            "To reinstall: call vm_eject_cdrom first (if ISO is still mounted), "
            "then vm_start with boot_iso=true."
        ),
    ),
]


def get_skill(name: str) -> Skill | None:
    """Look up a skill by name."""
    for skill in SKILLS:
        if skill.name == name:
            return skill
    return None


def list_skills() -> list[Skill]:
    """Return all available skills."""
    return list(SKILLS)
