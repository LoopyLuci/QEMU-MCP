"""Self-healing GUI entry point with hot reload and crash recovery.

Integrates:
- AtomicState for persistent state with snapshots
- ProcessGuardian for automatic restart and backup failover
- HotReloader for development-time code reloading
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

# Ensure paths are set up
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt

from gui.atomic_state import AtomicState
from gui.process_guardian import ProcessGuardian
from gui.hot_reloader import HotReloader
from gui.main_window import MainWindow
from gui.widgets import apply_global_theme

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "gui.log", mode="a"),
    ],
)
logger = logging.getLogger("qemu-mcp.main")


class SelfHealingApp:
    """Self-healing GUI application with state persistence and crash recovery."""

    def __init__(self, args: argparse.Namespace):
        self._args = args
        self._app: QApplication | None = None
        self._window: MainWindow | None = None
        self._state: AtomicState | None = None
        self._guardian: ProcessGuardian | None = None
        self._reloader: HotReloader | None = None
        self._snapshot_timer: QTimer | None = None
        self._health_timer: QTimer | None = None

    def run(self):
        """Run the self-healing application."""
        logger.info("Starting self-healing QEMU-MCP GUI")

        # Initialize atomic state
        self._state = AtomicState()
        self._state.create_snapshot("startup")

        # Check if recovering from crash
        if self._state.get("crash_recovery"):
            logger.info("Crash recovery detected, restoring last good state")
            self._state.restore_snapshot("last_good")

        # Create QApplication
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setApplicationName("QEMU-MCP")
        self._app.setApplicationVersion("1.0.0")
        apply_global_theme(self._app)

        # Create main window
        self._window = MainWindow()
        self._window.resize(1400, 900)
        self._window.show()

        # Restore window state
        self._restore_window_state()

        # Start periodic snapshots (every 30 seconds)
        self._snapshot_timer = QTimer(self._app)
        self._snapshot_timer.timeout.connect(self._take_snapshot)
        self._snapshot_timer.start(30000)

        # Start health check timer
        self._health_timer = QTimer(self._app)
        self._health_timer.timeout.connect(self._health_check)
        self._health_timer.start(5000)

        # Start hot reload if enabled
        if self._args.hot_reload:
            self._reloader = HotReloader(
                watch_dirs=[str(project_root / "gui")],
                on_reload=self._on_hot_reload,
                enabled=True,
            )
            self._reloader.start()

        # Mark as healthy
        self._state.set("crash_recovery", False)
        self._state.set("last_start", time.time())

        # Run event loop
        exit_code = self._app.exec_()

        # Cleanup
        self._cleanup()
        return exit_code

    def _restore_window_state(self):
        """Restore window geometry and state from atomic state."""
        if not self._window:
            return

        geometry = self._state.get("window_geometry")
        if geometry:
            try:
                self._window.setGeometry(
                    geometry.get("x", 100),
                    geometry.get("y", 100),
                    geometry.get("width", 1400),
                    geometry.get("height", 900),
                )
            except Exception:
                pass

    def _save_window_state(self):
        """Save window geometry and state to atomic state."""
        if not self._window:
            return

        try:
            geo = self._window.geometry()
            self._state.update({
                "window_geometry": {
                    "x": geo.x(),
                    "y": geo.y(),
                    "width": geo.width(),
                    "height": geo.height(),
                },
                "current_panel": getattr(self._window, "_current_panel", "dashboard"),
            })
        except Exception:
            pass

    def _take_snapshot(self):
        """Take a snapshot of current state."""
        if self._state:
            self._save_window_state()
            self._state.create_snapshot("last_good")
            logger.debug("State snapshot saved")

    def _health_check(self):
        """Periodic health check."""
        # Verify main window is responsive
        if self._window and not self._window.isVisible():
            logger.warning("Main window not visible, attempting recovery")
            self._window.show()
            self._window.raise_()

    def _on_hot_reload(self, changed_files: list[str]):
        """Handle hot reload of changed files."""
        logger.info("Hot reloading: %s", changed_files)
        # Save state before reload
        self._save_window_state()
        self._state.create_snapshot("pre_reload")

        # Reload changed modules
        for file_path in changed_files:
            module_name = file_path.replace("/", ".").replace(".py", "")
            if module_name in sys.modules:
                try:
                    importlib.reload(sys.modules[module_name])
                except Exception as e:
                    logger.error("Failed to reload %s: %s", module_name, e)

        # Restore state after reload
        self._restore_window_state()

    def _cleanup(self):
        """Cleanup on exit."""
        logger.info("Cleaning up self-healing app")

        if self._guardian:
            self._guardian.stop()

        if self._reloader:
            self._reloader.stop()

        if self._snapshot_timer:
            self._snapshot_timer.stop()

        if self._health_timer:
            self._health_timer.stop()

        if self._state:
            self._save_window_state()
            self._state.create_snapshot("last_good")
            self._state.set("crash_recovery", False)
            self._state.cleanup(keep_last=10)


def main():
    """Main entry point for self-healing GUI."""
    parser = argparse.ArgumentParser(description="QEMU-MCP Self-Healing GUI")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to .env config file (default: project .env)",
    )
    parser.add_argument(
        "--master-pass",
        type=str,
        default=None,
        dest="master_password",
        help="Master password for credential store",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run headless (no window, for testing)",
    )
    parser.add_argument(
        "--hot-reload",
        action="store_true",
        default=False,
        help="Enable hot reload of source files",
    )
    parser.add_argument(
        "--guardian",
        action="store_true",
        default=False,
        help="Enable process guardian (auto-restart)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help="Qt platform override (e.g., 'offscreen')",
    )
    parser.add_argument(
        "--standby",
        action="store_true",
        default=False,
        help="Run as standby backup instance",
    )
    args = parser.parse_args()

    # Apply CLI overrides
    if args.config:
        os.environ["VM_MCP_ENV_FILE"] = os.path.abspath(args.config)
    if args.master_password:
        os.environ["GUI_MASTER_PASSWORD"] = args.master_password
    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = args.platform
    elif args.headless:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    if args.headless:
        headless_main()
        return

    # Standby mode — run silently until promoted
    if args.standby:
        logger.info("Running in standby mode")
        standby_main()
        return

    # Run with optional guardian
    if args.guardian:
        run_with_guardian(args)
    else:
        app = SelfHealingApp(args)
        
        # Handle signals for clean shutdown
        def signal_handler(signum, frame):
            logger.info("Received signal %d, shutting down", signum)
            app._cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            exit_code = app.run()
        except KeyboardInterrupt:
            app._cleanup()
            exit_code = 0
        except Exception as e:
            logger.error("GUI crashed: %s", e)
            app._cleanup()
            exit_code = 1
        
        sys.exit(exit_code)


def headless_main():
    """Run headless (no window, for testing)."""
    logger.info("Running headless mode")
    app = QApplication.instance() or QApplication(sys.argv)
    apply_global_theme(app)
    window = MainWindow()
    window.show()
    # Run briefly then exit
    QTimer.singleShot(2000, app.quit)
    sys.exit(app.exec_())


def standby_main():
    """Run as a standby backup instance."""
    app = QApplication.instance() or QApplication(sys.argv)
    apply_global_theme(app)

    # In standby, we create the window but keep it hidden
    window = MainWindow()
    window.hide()

    # Check periodically if we should become primary
    check_timer = QTimer(app)
    check_timer.timeout.connect(lambda: check_promotion(window, app))
    check_timer.start(1000)

    sys.exit(app.exec_())


def check_promotion(window: MainWindow, app: QApplication):
    """Check if this standby should become primary."""
    state = AtomicState()
    role = os.environ.get("QEMU_MCP_ROLE", "primary")

    if role == "promoted":
        logger.info("Standby promoted to primary")
        window.show()
        window.raise_()
        os.environ["QEMU_MCP_ROLE"] = "primary"


def run_with_guardian(args: argparse.Namespace):
    """Run with process guardian for auto-restart."""
    main_script = str(project_root / "gui" / "__main__.py")

    guardian = ProcessGuardian(
        main_script=main_script,
        backup_count=1,
        max_restarts=10,
        restart_window=60,
    )

    guardian.set_crash_callback(
        lambda: logger.warning("Primary crashed, promoting backup")
    )
    guardian.set_restart_callback(
        lambda: logger.info("Primary restarted")
    )

    # Handle signals gracefully
    def signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down", signum)
        guardian.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    guardian.start()

    # Keep main thread alive
    try:
        while guardian.is_healthy:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        guardian.stop()


if __name__ == "__main__":
    main()
