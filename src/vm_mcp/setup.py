"""VM startup and QMP lifecycle management.

Handles launching QEMU with the correct arguments, waiting for QMP to
become available, and registering the QMP client in the module-level
context so tools can access it without passing it around.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Any
from pathlib import Path

from vm_mcp.config import VmMCPSettings, Secrets

logger = logging.getLogger(__name__)

# ── QMP client singleton ────────────────────────────────────────────────────────

_qmp_client: Any = None  # Set by connect_qmp; accessed by tools via get_qmp_client()


def get_qmp_client() -> Any:
    """Return the connected QMP client, or None if not connected."""
    return _qmp_client


def set_qmp_client(client: Any) -> None:
    """Set the QMP client singleton."""
    global _qmp_client
    _qmp_client = client


# ── QEMU launch arguments ───────────────────────────────────────────────────────

def build_qemu_args(
    settings: VmMCPSettings,
    start_iso: bool = False,
) -> list[str]:
    """Build the QEMU command line for the configured VM.

    Args:
        settings: Configuration from VmMCPSettings
        start_iso: If True, boot from ISO instead of disk

    Returns:
        List of QEMU arguments
    """
    qemu = settings.qemu_binary
    disk = settings.vm_disk_path
    iso = settings.vm_iso_path
    vcpus = settings.vm_cpus
    ram_mb = settings.vm_ram_mb
    display = settings.vm_display
    gl = settings.vm_gl
    name = settings.vm_name

    args: list[str] = [
        qemu,
        # Machine type
        "-machine", "q35",
        # CPUs
        "-smp", str(vcpus),
        # RAM
        "-m", str(ram_mb),
        # Accelerations — WHPX (Windows Hypervisor Platform)
        "-accel", "whpx",
        # CPU model — generic to maximize compatibility
        "-cpu", "host",
        # BIOS/UEFI — OVMF (QEMU bundles OVMF or user provides it)
        "-drive", "if=pflash,format=raw,readonly=on,file=C:/Program Files/qemu/share/edk2-x86_64-code.fd",
        # NIC — virtio-net-pci with user-mode networking
        "-netdev", "user,id=net0,hostfwd=tcp::2222-:22",
        "-device", "virtio-net-pci,netdev=net0",
        # Disk — virtio-blk with qcow2
        "-drive", f"if=virtio,format=qcow2,file={disk}",
        # Display
        "-display", display,
        "-vga", "virtio",
    ]

    # OpenGL support for SDL/gtk displays
    if gl and display in ("sdl", "gtk", "gtk,gl=on"):
        args.append("-device")
        args.append("virtio-vga-virgl")

    # Boot from ISO instead of disk (for install/repair)
    if start_iso and iso:
        args.extend([
            "-drive", f"file={iso},format=raw,media=cdrom,id=cdrom0",
            "-boot", "order=d",
        ])

    # QMP control socket — TCP for Windows compatibility
    if settings.qmp_socket_path:
        args.extend([
            "-qmp", f"unix:{settings.qmp_socket_path},server,nowait",
        ])
    else:
        args.extend([
            "-qmp", f"tcp:{settings.qmp_host}:{settings.qmp_port},server,nowait",
        ])

    # Serial console for debugging
    args.extend([
        "-serial", "stdio",
    ])

    # Don't show window title or force fullscreen
    args.extend([
        "-name", name,
    ])

    return args


# ── QMP connection ──────────────────────────────────────────────────────────────

class QMPClient:
    """Thin async wrapper around the QMP JSON protocol.

    QEMU's QMP protocol:
    1. Connect to socket
    2. Send '{"execute": "qmp_capabilities"}'
    3. Send commands: '{"execute": "<command>", "arguments": {...}}'
    4. Read responses: {"return": {...}, "error": {...}}
    """

    def __init__(self, uri: str, password: str | None = None, timeout_sec: float = 10.0):
        self.uri = uri
        self._password = password
        self._timeout = timeout_sec
        self._reader: Any = None
        self._writer: Any = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to QMP and finish handshake."""
        import asyncio

        if self.uri.startswith("unix:"):
            path = self.uri[6:]
            self._reader, self._writer = await asyncio.open_unix_connection(path)
        else:
            parts = self.uri.split(":")
            host = parts[1]
            port = int(parts[2])
            self._reader, self._writer = await asyncio.open_connection(host, port)

        self._connected = True

        # QMP handshake
        await self.send("qmp_capabilities")

        logger.info("QMP connected: %s", self.uri)

    async def send(self, cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a QMP command and return the parsed response."""
        if not self._connected:
            raise RuntimeError("QMP not connected")

        message: dict[str, Any] = {"execute": cmd}
        if args:
            message["arguments"] = args

        payload = json.dumps(message) + "\n"
        self._writer.write(payload.encode())
        await self._writer.drain()

        return await self._read_response()

    async def _read_response(self) -> dict[str, Any]:
        """Read one JSON response from QMP."""
        data = b""
        while not data.endswith(b"\n"):
            chunk = await asyncio.wait_for(
                self._reader.read(1),
                timeout=self._timeout,
            )
            if not chunk:
                raise RuntimeError("QMP connection closed")
            data += chunk

        response = json.loads(data.decode())
        if "error" in response:
            raise RuntimeError(f"QMP error: {response['error'].get('desc', 'unknown error')}")
        return response

    async def disconnect(self) -> None:
        """Close the QMP connection."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._connected = False
        logger.info("QMP disconnected: %s", self.uri)

    @property
    def is_connected(self) -> bool:
        return self._connected


async def connect_qmp(settings: VmMCPSettings, secrets: Secrets | None = None) -> QMPClient:
    """Connect to QMP and return a client."""
    if secrets is None:
        secrets = Secrets()

    uri = settings.qmp_uri()
    password = secrets.get_qmp_password()

    client = QMPClient(uri, password=password)
    await client.connect()
    set_qmp_client(client)
    return client


async def disconnect_qmp() -> None:
    """Disconnect QMP and clear the singleton."""
    client = get_qmp_client()
    if client:
        await client.disconnect()
    set_qmp_client(None)


# ── VM startup ──────────────────────────────────────────────────────────────────

async def start_vm(boot_iso: bool = False) -> str:
    """Start the QEMU VM and wait for QMP to be ready.

    Args:
        boot_iso: If True, boot from the installer ISO

    Returns:
        Status message
    """
    from vm_mcp.config import VmMCPSettings, Secrets

    settings = VmMCPSettings()
    secrets = Secrets.from_env()

    # Check if VM is already running via QMP
    client = get_qmp_client()
    if client and client.is_connected:
        status = await client.send("query-status")
        return f"VM already running: {status}"

    # Build arguments
    args = build_qemu_args(settings, start_iso=boot_iso)
    logger.info("Starting QEMU: %s", " ".join(args))

    # Launch QEMU as a subprocess
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for QMP to become available
    uri = settings.qmp_uri()
    max_wait = 30  # seconds
    start_time = time.monotonic()

    client = QMPClient(uri, password=secrets.get_qmp_password())
    while time.monotonic() - start_time < max_wait:
        try:
            client._reader, client._writer = await asyncio.open_connection(
                settings.qmp_host, settings.qmp_port
            ) if not uri.startswith("unix:") else await asyncio.open_unix_connection(uri[6:])
            break
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            await asyncio.sleep(0.5)

    if not (client._reader and client._writer):
        process.terminate()
        raise RuntimeError(f"QMP did not become available on {uri} within {max_wait}s")

    # Finish QMP handshake
    await client.send("qmp_capabilities")
    set_qmp_client(client)

    logger.info("QMP connected, QEMU PID %d", process.pid)

    # Auto-eject ISO after boot (if configured)
    if settings.auto_eject_iso and boot_iso:
        await asyncio.sleep(5)  # Give VM time to boot
        try:
            await client.send("eject", {"device": "ide0-cd0"})
        except Exception:
            pass

    return f"VM started successfully. QMP: {uri}. QEMU PID: {process.pid}"


async def stop_vm() -> str:
    """Gracefully stop the VM via QMP."""
    client = get_qmp_client()
    if not client or not client.is_connected:
        return "VM is not running (no QMP connection)"

    try:
        await client.send("system_powerdown")
        return "VM shutdown initiated (ACPI power button)"
    except Exception as e:
        logger.warning("system_powerdown failed, trying system_reset: %s", e)
        try:
            await client.send("system_reset")
            return "VM hard reset (system_powerdown failed)"
        except Exception as e2:
            return f"Failed to stop VM: {e2}"
    finally:
        await disconnect_qmp()
