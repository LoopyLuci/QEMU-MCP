#!/usr/bin/env python3
"""
VM-Harness On-Device CI/CD Pipeline — Common Utilities
──────────────────────────────────────────────────────
Shared helpers for desktop and Android pipeline tracks:
  - config loading (YAML)
  - logging / formatting
  - subprocess execution with timeout + output capture
  - file existence / size checks
  - SHA256 checksum generation
  - artifact packaging helpers
  - report generation
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Ensure the project root is on sys.path so 'ci' is importable as a package.
# This module may be run directly or imported by other CI modules.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── ANSI color helpers (for terminal UI) ─────────────────────────────────────

class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @classmethod
    def colorize(cls, text: str, code: str) -> str:
        return f"{code}{text}{cls.RESET}"


# ── Log level enum ────────────────────────────────────────────────────────────

class LogLevel:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3

    @classmethod
    def from_str(cls, s: str) -> int:
        return {
            "debug": cls.DEBUG,
            "info": cls.INFO,
            "warn": cls.WARN,
            "warning": cls.WARN,
            "error": cls.ERROR,
        }.get(s.lower(), cls.INFO)


# ── Colored logger ────────────────────────────────────────────────────────────

class Logger:
    """Simple colored logger with a current log level threshold."""

    def __init__(self, level: int = LogLevel.INFO):
        self.level = level
        self._emit_callbacks: list[Callable[[str, str, str], None]] = []

    def add_emit_callback(self, fn: Callable[[str, str, str], None]) -> None:
        """Register a callback for each log line: fn(level, color_code, message)."""
        self._emit_callbacks.append(fn)

    def _log(self, level: int, color: str, short: str, message: str) -> None:
        if level < self.level:
            return
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}] {short}"
        line = f"{Ansi.colorize(prefix, color)} {message}"
        for cb in self._emit_callbacks:
            try:
                cb(level, color, message)
            except Exception:
                pass

    def debug(self, message: str) -> None:
        self._log(LogLevel.DEBUG, Ansi.CYAN, "DEBUG", message)

    def info(self, message: str) -> None:
        self._log(LogLevel.INFO, Ansi.BLUE, "INFO", message)

    def warn(self, message: str) -> None:
        self._log(LogLevel.WARN, Ansi.YELLOW, "WARN", message)

    def error(self, message: str) -> None:
        self._log(LogLevel.ERROR, Ansi.RED, "ERROR", message)

    def success(self, message: str) -> None:
        self._log(LogLevel.INFO, Ansi.GREEN, "OK", message)

    def fail(self, message: str) -> None:
        self._log(LogLevel.ERROR, Ansi.RED, "FAIL", message)

    def section(self, message: str) -> None:
        """Print a section header."""
        line = f"{'=' * 60}"
        print(f"\n{Ansi.colorize(line, Ansi.BOLD)}")
        print(f"{Ansi.colorize(f'  {message}', Ansi.BOLD)}")
        print(f"{Ansi.colorize(line, Ansi.BOLD)}\n")

    def subsection(self, message: str) -> None:
        print(f"\n{Ansi.colorize(f'── {message} ──', Ansi.BOLD)}\n")

    def divider(self) -> None:
        print(f"{Ansi.colorize('-' * 60, Ansi.DIM)}")


# ── Config loading ────────────────────────────────────────────────────────────

def load_config(path: str | Path) -> dict[str, Any]:
    """Load the CI config YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback: minimal YAML parser for our config structure
        return _minimal_yaml_load(path)


def _minimal_yaml_load(path: Path) -> dict[str, Any]:
    """Minimal YAML loader for flat-ish config (no full YAML lib needed)."""
    import re as _re

    result: dict[str, Any] = {}
    current_section: str | None = None
    current_subsection: str | None = None
    current_dict: dict[str, Any] | None = None
    stack: list[tuple[str, dict[str, Any]]] = []

    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())

            # Top-level key: "desktop:" or "pipeline:"
            if indent == 0 and stripped.endswith(":"):
                key = stripped[:-1].strip()
                result[key] = {}
                current_section = key
                current_subsection = None
                current_dict = result[key]
                continue

            if current_section is None:
                continue

            # Sub-key: "  prepare:" or "    check_python: true"
            if indent == 2 and stripped.endswith(":"):
                sub_key = stripped[:-1].strip()
                current_section_obj = result[current_section]
                if not isinstance(current_section_obj, dict):
                    continue
                current_section_obj[sub_key] = {}
                current_subsection = sub_key
                current_dict = current_section_obj[sub_key]
                stack.append((current_section, current_dict))
                continue

            if indent == 4 and stripped.endswith(":"):
                sub_sub_key = stripped[:-1].strip()
                if current_dict is not None:
                    current_dict[sub_sub_key] = {}
                    current_dict = current_dict[sub_sub_key]
                continue

            # Key: value
            if ":" in stripped:
                key_part, _, value_part = stripped.partition(":")
                key = key_part.strip()
                value = value_part.strip()
                target = current_dict
                if target is None:
                    continue
                if value == "":
                    target[key] = {}
                    current_dict = target[key]
                elif value.lower() == "true":
                    target[key] = True
                elif value.lower() == "false":
                    target[key] = False
                elif value.isdigit():
                    target[key] = int(value)
                else:
                    try:
                        target[key] = float(value)
                    except ValueError:
                        target[key] = value

            # List item: "      - 'tests/...'"
            if stripped.lstrip().startswith("- "):
                item = stripped.strip()[2:].strip()
                target_list: list[Any] = []
                if isinstance(current_dict, list):
                    target_list = current_dict
                else:
                    # Find the parent list — we don't track lists in this minimal parser
                    pass
                # For our config, lists are under specific keys — handled by the real YAML loader
                # This fallback won't parse lists perfectly; real YAML lib is preferred
                continue

    return result


# ── Process execution ─────────────────────────────────────────────────────────

@dataclass
class ProcessResult:
    """Result of running a subprocess."""
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    succeeded: bool
    command: str
    cwd: str | None


def run_command(
    cmd: str | list[str],
    cwd: str | Path | None = None,
    timeout_s: float = 300,
    check: bool = False,
    env: dict[str, str] | None = None,
    logger: Logger | None = None,
    capture: bool = True,
) -> ProcessResult:
    """Run a shell command and return structured result.

    Args:
        cmd: Command string (run via shell=True) or list (run directly).
        cwd: Working directory.
        timeout_s: Max seconds to wait.
        check: If True, raise on non-zero exit.
        env: Additional env vars (merged with os.environ).
        logger: Optional logger for output.
        capture: If False, stream output to terminal directly.
    """
    cwd = str(cwd) if cwd else None
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    start = time.monotonic()
    try:
        if isinstance(cmd, str):
            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=cwd,
                env=merged_env,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                text=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=merged_env,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                text=True,
            )

        if capture:
            try:
                stdout, stderr = proc.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                stderr = (stderr or "") + f"\n[PROCESS TIMEOUT after {timeout_s}s]"
                if logger:
                    logger.error(f"Command timed out after {timeout_s}s: {cmd_str}")
        else:
            # Stream mode — wait without capturing
            proc.wait(timeout=timeout_s)
            stdout = ""
            stderr = ""

        duration = time.monotonic() - start
        result = ProcessResult(
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_s=round(duration, 2),
            succeeded=proc.returncode == 0,
            command=cmd_str,
            cwd=cwd,
        )

        if logger:
            if result.succeeded:
                logger.success(f"[{round(duration, 1)}s] {cmd_str}")
            else:
                logger.fail(f"[{round(duration, 1)}s] {cmd_str} (exit {proc.returncode})")

        if check and not result.succeeded:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd_str, output=stdout, stderr=stderr
            )

        return result

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        result = ProcessResult(
            returncode=-1,
            stdout="",
            stderr=f"Process timed out after {timeout_s}s",
            duration_s=round(duration, 2),
            succeeded=False,
            command=cmd_str,
            cwd=cwd,
        )
        if logger:
            logger.error(f"Command timed out: {cmd_str}")
        if check:
            raise
        return result
    except Exception as e:
        duration = time.monotonic() - start
        if logger:
            logger.error(f"Command failed: {cmd_str} — {e}")
        return ProcessResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            duration_s=round(duration, 2),
            succeeded=False,
            command=cmd_str,
            cwd=cwd,
        )


# ── File helpers ──────────────────────────────────────────────────────────────

def file_exists(path: str | Path) -> bool:
    return Path(path).exists()


def file_size(path: str | Path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    return p.stat().st_size


def file_size_human(path: str | Path) -> str:
    size = file_size(path)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def sha256_file(path: str | Path) -> str:
    """Compute SHA256 hex digest of a file."""
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_string(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def list_files(directory: str | Path, pattern: str = "**/*", recursive: bool = True) -> list[Path]:
    """List files matching a glob pattern under a directory. Recursive by default."""
    p = Path(directory)
    if not p.exists():
        return []
    return sorted(p.rglob(pattern))


def copy_file(src: str | Path, dst: str | Path) -> bool:
    try:
        shutil.copy2(Path(src), Path(dst))
        return True
    except Exception:
        return False


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── YAML generation for report ────────────────────────────────────────────────

def write_yaml_report(path: str | Path, data: dict[str, Any]) -> None:
    """Write a YAML report. Falls back to JSON if PyYAML not available."""
    try:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    except ImportError:
        write_json_report(path.with_suffix(".json"), data)


def write_json_report(path: str | Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ── Text report helpers ───────────────────────────────────────────────────────

def write_text_report(path: str | Path, lines: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def duration_human(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def check_import(module_name: str) -> bool:
    """Check if a Python module is importable without raising."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# ── Git helpers ───────────────────────────────────────────────────────────────

def git_status(root: str | Path) -> str:
    """Return 'clean' or 'dirty'."""
    r = run_command(["git", "status", "--porcelain"], cwd=root)
    return "clean" if r.succeeded and not r.stdout.strip() else "dirty"


def git_version_tag(root: str | Path) -> str | None:
    """Get the latest git tag, or None."""
    r = run_command(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=root,
    )
    if r.succeeded:
        return r.stdout.strip()
    return None


def git_head_commit(root: str | Path) -> str:
    r = run_command(["git", "rev-parse", "HEAD"], cwd=root)
    if r.succeeded:
        return r.stdout.strip()[:12]
    return "unknown"


def git_diff_summary(root: str | Path) -> str:
    """One-line summary of uncommitted changes."""
    r = run_command(["git", "diff", "--stat", "HEAD"], cwd=root)
    if r.succeeded and r.stdout.strip():
        return r.stdout.strip().split("\n")[-1]
    return "no changes"


# ── Version helpers ───────────────────────────────────────────────────────────

def get_desktop_version(root: str | Path) -> str:
    """Read version from pyproject.toml."""
    pyproject = Path(root) / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    content = pyproject.read_text(encoding="utf-8")
    for line in content.split("\n"):
        if line.strip().startswith("version"):
            _, _, val = line.partition("=")
            return val.strip().strip('"').strip("'")
    return "0.0.0"


# ── Phase result tracking ─────────────────────────────────────────────────────

@dataclass
class PhaseResult:
    """Result of a single CI phase."""
    track: str          # "desktop" or "android"
    phase: str          # "prepare", "preflight", "test", "build", "deploy"
    status: str         # "passed", "failed", "skipped"
    duration_s: float
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class TrackResult:
    """Aggregated result for one track."""
    track: str
    phases: list[PhaseResult] = field(default_factory=list)
    overall_status: str = "pending"  # "passed", "failed", "skipped"
    start_time: str = ""
    end_time: str = ""


@dataclass
class PipelineResult:
    """Complete pipeline result."""
    tracks: list[TrackResult] = field(default_factory=list)
    overall_status: str = "pending"
    start_time: str = ""
    end_time: str = ""
    config: dict[str, Any] = field(default_factory=dict)


def deserialize_pipeline_result(data: dict[str, Any]) -> PipelineResult:
    """Reconstruct a PipelineResult from a JSON dict."""
    r = PipelineResult(
        overall_status=data.get("overall_status", "unknown"),
        start_time=data.get("start_time", now_iso()),
        end_time=data.get("end_time", now_iso()),
        config=data.get("config_summary", {}),
    )
    for t_data in data.get("tracks", []):
        tr = TrackResult(
            track=t_data.get("track", "unknown"),
            overall_status=t_data.get("overall_status", "unknown"),
            start_time=t_data.get("start_time", ""),
            end_time=t_data.get("end_time", ""),
        )
        for p_data in t_data.get("phases", []):
            tr.phases.append(PhaseResult(
                track=tr.track,
                phase=p_data.get("phase", ""),
                status=p_data.get("status", "unknown"),
                duration_s=p_data.get("duration_s", 0),
                message=p_data.get("message", ""),
                details=p_data.get("details", {}),
                error=p_data.get("error", ""),
            ))
        r.tracks.append(tr)
    return r
