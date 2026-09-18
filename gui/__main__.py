#!/usr/bin/env python3
"""QEMU-MCP GUI — Entry point.

Starts the PyQt5 desktop application for QEMU/VM control.
Usage:
    python -m vm_mcp.gui
    python -m gui  (when installed)
"""

from __future__ import annotations

import sys
import os

# Ensure src is on path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("QEMU-MCP")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("QEMU-MCP")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
