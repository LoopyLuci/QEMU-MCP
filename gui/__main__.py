#!/usr/bin/env python3
"""QEMU-MCP GUI — Entry point.

Starts the PyQt5 desktop application for QEMU/VM control.
Supports CLI overrides for config file and credential master password.

Usage:
    python -m vm_mcp.gui                  # normal launch
    python -m vm_mcp.gui --config path    # use alternate .env file
    python -m vm_mcp.gui --headless       # headless mode (no window)
    python -m vm_mcp.gui --master-pass X  # credential store master password
    python -m vm_mcp.gui --help           # show options
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure src and project root are on path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui.main_window import MainWindow
from gui.widgets import apply_global_theme
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="vm-mcp-gui",
        description="QEMU-MCP GUI — desktop interface for QEMU/VM control",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to .env config file (default: project .env)",
    )
    parser.add_argument(
        "--master-pass",
        metavar="STR",
        default=None,
        dest="master_password",
        help="Master password for the GUI credential store (Fernet encryption)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run headless (no window, useful for smoke testing)",
    )
    parser.add_argument(
        "--platform",
        metavar="STR",
        default=None,
        help="Qt platform plugin override (e.g. 'offscreen' for headless)",
    )
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(sys.argv if argv is None else argv)

    # Apply CLI overrides to environment
    if args.config:
        os.environ["VM_MCP_ENV_FILE"] = os.path.abspath(args.config)
    if args.master_password:
        os.environ["GUI_MASTER_PASSWORD"] = args.master_password
    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = args.platform
    elif args.headless:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication(sys.argv)
    app.setApplicationName("QEMU-MCP")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("QEMU-MCP")

    # Apply dark theme
    apply_global_theme(app)

    window = MainWindow()

    if args.headless:
        window.show()
        # In headless mode, run briefly then exit
        import time

        time.sleep(1)
        window.close()
        sys.exit(0)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
