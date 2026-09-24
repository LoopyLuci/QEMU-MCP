"""VM-Harness CLI — command-line interface for agent access.

Usage:
    qemu-mcp status              # Show system status
    qemu-mcp vm list             # List VMs
    qemu-mcp vm start <name>     # Start VM
    qemu-mcp vm stop <name>      # Stop VM
    qemu-mcp vm restart <name>   # Restart VM
    qemu-mcp snapshot list       # List snapshots
    qemu-mcp snapshot create <name>  # Create snapshot
    qemu-mcp iso list            # List ISOs
    qemu-mcp config get          # Get config
    qemu-mcp api start           # Start REST API server
    qemu-mcp gui                 # Launch GUI
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src and project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "src"))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from vm_mcp.config import VmMCPSettings, Secrets


def cmd_status(args):
    """Show system status."""
    settings = VmMCPSettings()
    status = {
        "server": "qemu-mcp",
        "version": "1.0.0",
        "qmp_host": settings.qmp_host,
        "qmp_port": settings.qmp_port,
        "vm_name": settings.vm_name,
        "vm_disk_path": str(settings.vm_disk_path) if settings.vm_disk_path else None,
    }
    print(json.dumps(status, indent=2))


def cmd_vm_list(args):
    """List VMs."""
    settings = VmMCPSettings()
    vms = [{
        "name": settings.vm_name,
        "disk_path": str(settings.vm_disk_path) if settings.vm_disk_path else None,
        "qmp_port": settings.qmp_port,
    }]
    print(json.dumps({"vms": vms}, indent=2))


def cmd_vm_start(args):
    """Start VM."""
    print(json.dumps({"status": "not_implemented", "message": "Use QMP bridge"}))


def cmd_vm_stop(args):
    """Stop VM."""
    print(json.dumps({"status": "not_implemented", "message": "Use QMP bridge"}))


def cmd_vm_restart(args):
    """Restart VM."""
    print(json.dumps({"status": "not_implemented", "message": "Use QMP bridge"}))


def cmd_snapshot_list(args):
    """List snapshots."""
    import subprocess
    settings = VmMCPSettings()
    disk = settings.vm_disk_path
    if not disk or not Path(disk).exists():
        print(json.dumps({"error": "VM disk not found"}))
        return
    qemu_img = Path(settings.qemu_binary).parent / "qemu-img.exe"
    if not qemu_img.exists():
        qemu_img = "qemu-img"
    result = subprocess.run(
        [str(qemu_img), "snapshot", "-l", str(disk)],
        capture_output=True, text=True, timeout=10
    )
    print(json.dumps({"snapshots": result.stdout.strip()}, indent=2))


def cmd_snapshot_create(args):
    """Create snapshot."""
    import subprocess
    settings = VmMCPSettings()
    disk = settings.vm_disk_path
    if not disk or not Path(disk).exists():
        print(json.dumps({"error": "VM disk not found"}))
        return
    name = args.name or "snapshot-" + str(int(__import__("time").time()))
    result = subprocess.run(
        ["qemu-img", "snapshot", "-c", name, str(disk)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(json.dumps({"status": "ok", "name": name}))
    else:
        print(json.dumps({"error": result.stderr}))


def cmd_iso_list(args):
    """List ISOs."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from gui.iso_manager import ISOManager
    manager = ISOManager()
    isos = manager.scan_isos()
    print(json.dumps({"isos": isos}, indent=2))


def cmd_config_get(args):
    """Get config."""
    settings = VmMCPSettings()
    config = {
        "qmp_host": settings.qmp_host,
        "qmp_port": settings.qmp_port,
        "vm_name": settings.vm_name,
        "vm_ram_mb": settings.vm_ram_mb,
        "vm_cpus": settings.vm_cpus,
        "vm_display": settings.vm_display,
    }
    print(json.dumps(config, indent=2))


def cmd_api_start(args):
    """Start REST API server."""
    from gui.api_server import QMCPAPIServer
    server = QMCPAPIServer(host="127.0.0.1", port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def cmd_gui(args):
    """Launch GUI."""
    from gui.__main__ import main
    main()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="qemu-mcp",
        description="VM-Harness: Control QEMU virtual machines"
    )
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show system status")

    # vm
    vm_parser = subparsers.add_parser("vm", help="VM management")
    vm_sub = vm_parser.add_subparsers(dest="vm_command")
    vm_sub.add_parser("list", help="List VMs")
    vm_start = vm_sub.add_parser("start", help="Start VM")
    vm_start.add_argument("name", nargs="?", help="VM name")
    vm_stop = vm_sub.add_parser("stop", help="Stop VM")
    vm_stop.add_argument("name", nargs="?", help="VM name")
    vm_restart = vm_sub.add_parser("restart", help="Restart VM")
    vm_restart.add_argument("name", nargs="?", help="VM name")

    # snapshot
    snap_parser = subparsers.add_parser("snapshot", help="Snapshot management")
    snap_sub = snap_parser.add_subparsers(dest="snap_command")
    snap_sub.add_parser("list", help="List snapshots")
    snap_create = snap_sub.add_parser("create", help="Create snapshot")
    snap_create.add_argument("name", nargs="?", help="Snapshot name")

    # iso
    subparsers.add_parser("iso", help="List ISOs").add_argument("action", nargs="?", default="list")

    # providers
    providers_parser = subparsers.add_parser("providers", help="Manage AI providers")
    providers_sub = providers_parser.add_subparsers(dest="providers_command")
    providers_sub.add_parser("list", help="List providers")
    providers_sub.add_parser("usage", help="Show usage summary")

    # config
    subparsers.add_parser("config", help="Get configuration").add_argument("action", nargs="?", default="get")

    # api
    api_parser = subparsers.add_parser("api", help="REST API server")
    api_parser.add_argument("--port", type=int, default=8080, help="API port")

    # gui
    subparsers.add_parser("gui", help="Launch GUI")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "vm": {
            "list": cmd_vm_list,
            "start": cmd_vm_start,
            "stop": cmd_vm_stop,
            "restart": cmd_vm_restart,
        },
        "snapshot": {
            "list": cmd_snapshot_list,
            "create": cmd_snapshot_create,
        },
        "iso": cmd_iso_list,
        "config": cmd_config_get,
        "api": cmd_api_start,
        "gui": cmd_gui,
    }

    if not args.command:
        parser.print_help()
        return

    handler = commands.get(args.command)
    if isinstance(handler, dict):
        if args.command == "vm":
            sub = getattr(args, "vm_command", None)
        elif args.command == "snapshot":
            sub = getattr(args, "snap_command", None)
        else:
            sub = None
        if not sub:
            parser.parse_args([args.command, "--help"])
            return
        handler = handler.get(sub)
        if not handler:
            parser.parse_args([args.command, "--help"])
            return

    handler(args)


if __name__ == "__main__":
    main()
