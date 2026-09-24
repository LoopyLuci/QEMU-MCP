"""Hypervisor abstraction layer — unified VM lifecycle interface across backends.

This package provides a single ``HypervisorBackend`` ABC that all concrete
backends implement, plus a ``HypervisorRegistry`` that auto-detects the best
available backend on the current host.

Supported backends:
- QEMU (QMP over TCP/Unix socket, SPICE/VNC display)
- VMware (vmrun CLI)
- VirtualBox (VBoxManage CLI)
- WSL (wsl.exe)
- Hyper-V (PowerShell cmdlets)
- KVM (libvirt/qemu on Linux)
"""

from vm_harness.hypervisor.backend import (
    HypervisorBackend,
    VMConfig,
    VMStatus,
    VMState,
    VMMetrics,
    VMDisplay,
    VMNetwork,
    VMSnapshot,
    VMConsole,
    VMGuestInfo,
    HypervisorError,
    VMNotFoundError,
    VMAlreadyRunningError,
    VMNotRunningError,
    BackendNotAvailableError,
)
from vm_harness.hypervisor.registry import HypervisorRegistry

__all__ = [
    "HypervisorBackend",
    "VMConfig",
    "VMStatus",
    "VMState",
    "VMMetrics",
    "VMDisplay",
    "VMNetwork",
    "VMSnapshot",
    "VMConsole",
    "VMGuestInfo",
    "HypervisorError",
    "VMNotFoundError",
    "VMAlreadyRunningError",
    "VMNotRunningError",
    "BackendNotAvailableError",
    "HypervisorRegistry",
]
