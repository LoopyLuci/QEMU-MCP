"""VM-Harness GUI — single-instance, self-managing, crash-proof entry point.

Uses project .venv with pythonw.exe (no console window).
Runs headless server + streaming bridge as daemon threads.
Full resilience: crash handler, atomic state, hot reload, failover, self-healing.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: Suppress ALL CLI console windows on Windows
# Monkeypatch subprocess BEFORE any other imports
# ═══════════════════════════════════════════════════════════════════════════════
import os
import sys
if sys.platform == "win32":
    import subprocess as _subprocess
    _CREATE_NO_WINDOW = 0x08000000
    _SW_HIDE = 0

    _orig_popen_init = _subprocess.Popen.__init__
    def _Popen_init_no_window(self, *args, **kwargs):
        kwargs.setdefault("creationflags", _CREATE_NO_WINDOW)
        si = _subprocess.STARTUPINFO()
        si.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE
        kwargs.setdefault("startupinfo", si)
        _orig_popen_init(self, *args, **kwargs)
    _subprocess.Popen.__init__ = _Popen_init_no_window

    _orig_run = _subprocess.run
    def _run_no_window(*args, **kwargs):
        kwargs.setdefault("creationflags", _CREATE_NO_WINDOW)
        si = _subprocess.STARTUPINFO()
        si.dwFlags |= _subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE
        kwargs.setdefault("startupinfo", si)
        return _orig_run(*args, **kwargs)
    _subprocess.run = _run_no_window

    for _name in ("call", "check_call", "check_output"):
        _orig = getattr(_subprocess, _name)
        setattr(_subprocess, _name, lambda *a, _o=_orig, **kw: _o(*a, **{**kw, "creationflags": kw.get("creationflags", _CREATE_NO_WINDOW)}))

import argparse
import atexit
import asyncio
import logging
import os
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Ensure paths are set up BEFORE any project imports
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ═══════════════════════════════════════════════════════════════════════════════
# Logging setup — file + optional console (no console for pythonw.exe)
# ═══════════════════════════════════════════════════════════════════════════════

LOG_DIR = project_root / "logs"
LOG_DIR.mkdir(exist_ok=True)

_file_handler = RotatingFileHandler(
    LOG_DIR / "vmharness.log", mode="a",
    maxBytes=5 * 1024 * 1024, backupCount=3,
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_file_handler],
)
logger = logging.getLogger("vmharness.gui")

# ═══════════════════════════════════════════════════════════════════════════════
# Single-instance lock
# ═══════════════════════════════════════════════════════════════════════════════

_LOCK_FILE = script_dir / ".vmharness_gui.lock"


def _is_pid_running(pid: int) -> bool:
    """Check if a Windows process with given PID is alive."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False

    try:
        exit_code = wintypes.DWORD()
        result = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        if not result:
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _acquire_single_instance() -> bool:
    """Acquire single-instance lock. Returns True if we own it."""
    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text().strip())
            if _is_pid_running(pid):
                logger.info("VM-Harness GUI already running (PID %d) — exiting", pid)
                return False
        except (ValueError, OSError):
            pass
        try:
            _LOCK_FILE.unlink()
        except OSError:
            pass

    _LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    """Release the single-instance lock."""
    try:
        if _LOCK_FILE.exists():
            pid = int(_LOCK_FILE.read_text().strip())
            if pid == os.getpid():
                _LOCK_FILE.unlink()
    except (ValueError, OSError):
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Service threads
# ═══════════════════════════════════════════════════════════════════════════════

_stop_event = threading.Event()
_headless_loop: asyncio.AbstractEventLoop | None = None
_bridge_loop: asyncio.AbstractEventLoop | None = None


def _run_headless_server():
    """Run headless server in its own event loop."""
    global _headless_loop
    loop = asyncio.new_event_loop()
    _headless_loop = loop
    asyncio.set_event_loop(loop)
    try:
        async def _run():
            from headless_server import main as headless_main
            # headless_main is sync; run in executor to keep loop responsive
            await loop.run_in_executor(None, headless_main)
        loop.run_until_complete(_run())
    except (SystemExit, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error("Headless server error: %s", e)
    finally:
        _headless_loop = None
        loop.close()


def _run_streaming_bridge():
    """Run streaming bridge with graceful shutdown support."""
    global _bridge_loop
    loop = asyncio.new_event_loop()
    _bridge_loop = loop
    asyncio.set_event_loop(loop)
    try:
        async def _run():
            from streaming_bridge import main as bridge_main
            await bridge_main()
        loop.run_until_complete(_run())
    except (SystemExit, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error("Streaming bridge error: %s", e)
    finally:
        _bridge_loop = None
        loop.close()


def _stop_background_threads():
    """Signal threads to stop and gracefully shut down their event loops."""
    _stop_event.set()
    # Stop event loops from the main thread (thread-safe)
    for loop in (_headless_loop, _bridge_loop):
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)


# ═══════════════════════════════════════════════════════════════════════════════
# GUI Application
# ═══════════════════════════════════════════════════════════════════════════════

def run_gui(args: argparse.Namespace) -> int:
    """Run the GUI event loop with full resilience."""
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
    from gui.main_window import MainWindow
    from gui.widgets import apply_global_theme
    from gui.resilience import get_orchestrator

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("VM-Harness")
    app.setApplicationVersion("2.0.0")
    apply_global_theme(app)

    window = MainWindow()
    window.resize(1400, 900)
    window.show()

    # Start self-healing orchestrator
    orchestrator = get_orchestrator()
    orchestrator.start()

    # Health check timer — ensures window stays responsive
    health_timer = QTimer(app)
    health_timer.timeout.connect(lambda: _health_check(window))
    health_timer.start(5000)

    # State save timer — atomic state persistence
    state_timer = QTimer(app)
    state_timer.timeout.connect(lambda: _save_state(window))
    state_timer.start(30000)

    # Run event loop
    try:
        exit_code = app.exec_()
    except Exception as e:
        logger.critical("GUI event loop crashed: %s", e)
        import traceback
        logger.critical("Crash trace:\n%s", traceback.format_exc())
        exit_code = 1

    # Cleanup
    health_timer.stop()
    state_timer.stop()
    orchestrator.stop()
    _release_lock()
    return exit_code


def _health_check(window):
    """Ensure main window is visible and responsive."""
    if window and not window.isVisible():
        logger.warning("Main window not visible — restoring")
        window.show()
        window.raise_()


def _save_state(window):
    """Save atomic state for crash recovery."""
    try:
        from gui.resilience import get_orchestrator
        orchestrator = get_orchestrator()
        state = orchestrator.atomic_state
        # Save current window state
        if window and window.isVisible():
            state.save(type("State", (), {
                "name": "gui_window",
                "status": "running",
                "pid": os.getpid(),
                "config": {
                    "geometry": window.saveGeometry().toHex().data().decode(),
                    "visible": window.isVisible(),
                },
                "last_updated": __import__("datetime").datetime.now().isoformat(),
                "checksum": "",
            })())
    except Exception as e:
        logger.error("Failed to save state: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point — single-instance enforced, crash-proof, no console window."""

    # Parse args first
    parser = argparse.ArgumentParser(description="VM-Harness GUI")
    parser.add_argument("--config", type=str, default=None, help="Path to .env file")
    parser.add_argument("--master-pass", type=str, default=None, dest="master_password")
    parser.add_argument("--headless", action="store_true", default=False)
    parser.add_argument("--platform", type=str, default=None, help="Qt platform override")
    parser.add_argument("--dev", action="store_true", default=False, help="Enable hot-reload dev mode")
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
    if args.dev:
        os.environ["VM_HARNESS_DEV"] = "1"

    # Enforce single instance BEFORE anything else
    if not _acquire_single_instance():
        sys.exit(0)

    # Handle signals for clean shutdown
    def signal_handler(signum, frame):
        logger.info("Received signal %d — shutting down", signum)
        _release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Register atexit cleanup
    atexit.register(_release_lock)

    # Start service threads (daemon — will be killed on exit)
    headless_thread = None
    bridge_thread = None
    if not args.headless:
        headless_thread = threading.Thread(target=_run_headless_server, daemon=True)
        headless_thread.start()

        bridge_thread = threading.Thread(target=_run_streaming_bridge, daemon=True)
        bridge_thread.start()

    # Run headless or GUI
    if args.headless:
        exit_code = _run_headless(args)
    else:
        try:
            exit_code = run_gui(args)
        except Exception as e:
            logger.critical("GUI crashed: %s", e)
            import traceback
            logger.critical("Crash trace:\n%s", traceback.format_exc())
            _release_lock()
            sys.exit(1)

    # Stop background threads gracefully before exit
    _stop_background_threads()
    if headless_thread is not None:
        headless_thread.join(timeout=3)
    if bridge_thread is not None:
        bridge_thread.join(timeout=3)
    _release_lock()
    os._exit(exit_code)


def _run_headless(args: argparse.Namespace) -> int:
    """Run headless — validate initialization without event loop."""
    from PyQt5.QtWidgets import QApplication
    from gui.main_window import MainWindow
    from gui.widgets import apply_global_theme

    logger.info("Running headless mode")
    app = QApplication.instance() or QApplication(sys.argv)
    apply_global_theme(app)
    window = MainWindow()
    window.show()
    logger.info("Headless validation: QApplication, theme, MainWindow all initialized")
    window.close()
    window.deleteLater()
    app.quit()
    logger.info("Headless mode complete")
    return 0


if __name__ == "__main__":
    main()
