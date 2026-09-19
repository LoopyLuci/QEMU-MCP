"""Multi-VM Manager — control multiple QEMU instances."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

VM_CONFIGS_DIR = Path.home() / ".qemu-mcp" / "vm-configs"
VM_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


class VMConfig:
    """Configuration for a single VM."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "VMConfig":
        return cls(name, data)

    def to_dict(self) -> dict[str, Any]:
        return self.config


class MultiVMManager:
    """Manage multiple VM configurations and QEMU instances."""

    def __init__(self):
        self._configs: dict[str, VMConfig] = {}
        self._running: dict[str, subprocess.Popen] = {}
        self._load_configs()

    def _load_configs(self):
        """Load VM configs from disk."""
        for config_file in VM_CONFIGS_DIR.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                name = config_file.stem
                self._configs[name] = VMConfig(name, data)
            except Exception:
                pass

    def _save_config(self, name: str):
        """Save a VM config to disk."""
        if name not in self._configs:
            return
        config_file = VM_CONFIGS_DIR / f"{name}.json"
        with open(config_file, 'w') as f:
            json.dump(self._configs[name].to_dict(), f, indent=2)

    def add_vm(self, name: str, config: dict[str, Any]) -> bool:
        """Add a new VM configuration."""
        if name in self._configs:
            return False
        self._configs[name] = VMConfig(name, config)
        self._save_config(name)
        return True

    def remove_vm(self, name: str) -> bool:
        """Remove a VM configuration."""
        if name not in self._configs:
            return False
        if name in self._running:
            self.stop_vm(name)
        del self._configs[name]
        config_file = VM_CONFIGS_DIR / f"{name}.json"
        if config_file.exists():
            config_file.unlink()
        return True

    def get_vm(self, name: str) -> VMConfig | None:
        """Get a VM configuration."""
        return self._configs.get(name)

    def list_vms(self) -> list[str]:
        """List all VM names."""
        return list(self._configs.keys())

    def get_config(self, name: str) -> dict[str, Any] | None:
        """Get config for a VM."""
        vm = self._configs.get(name)
        return vm.to_dict() if vm else None

    def update_config(self, name: str, updates: dict[str, Any]):
        """Update VM configuration."""
        if name in self._configs:
            self._configs[name].config.update(updates)
            self._save_config(name)

    def start_vm(self, name: str) -> bool:
        """Start a VM."""
        config = self.get_config(name)
        if not config:
            return False

        args = self._build_qemu_args(config)
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self._running[name] = proc
            return True
        except Exception:
            return False

    def stop_vm(self, name: str) -> bool:
        """Stop a running VM."""
        if name not in self._running:
            return False
        try:
            self._running[name].terminate()
            self._running[name].wait(timeout=5)
            del self._running[name]
            return True
        except Exception:
            return False

    def is_running(self, name: str) -> bool:
        """Check if a VM is running."""
        if name not in self._running:
            return False
        return self._running[name].poll() is None

    def get_pid(self, name: str) -> int | None:
        """Get PID of running VM."""
        if not self.is_running(name):
            return None
        return self._running[name].pid

    @staticmethod
    def _build_qemu_args(config: dict[str, Any]) -> list[str]:
        """Build QEMU command line from config."""
        qemu = config.get("qemu_binary", r"C:\Program Files\qemu\qemu-system-x86_64.exe")
        disk = config.get("disk_path", "")
        vcpus = str(config.get("cpus", 2))
        ram_mb = str(config.get("ram_mb", 4096))
        display = config.get("display", "sdl")
        name = config.get("name", "vm")
        qmp_port = str(config.get("qmp_port", 4444))

        args = [
            qemu,
            "-machine", "q35",
            "-smp", vcpus,
            "-m", ram_mb,
            "-accel", "whpx",
            "-cpu", "host",
            "-drive", r"if=pflash,format=raw,readonly=on,file=C:/Program Files/qemu/share/edk2-x86_64-code.fd",
            "-netdev", f"user,id=net0,hostfwd=tcp::{2222 + hash(name) % 100}-:22",
            "-device", "virtio-net-pci,netdev=net0",
            "-drive", f"if=virtio,format=qcow2,file={disk}",
            "-display", display,
            "-vga", "virtio",
            "-qmp", f"tcp:127.0.0.1:{qmp_port},server,nowait",
            "-serial", "stdio",
            "-name", name,
        ]
        return args
