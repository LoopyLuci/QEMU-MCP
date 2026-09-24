#!/usr/bin/env python3
"""
Sprint 3 — elevate bare `except Exception:` to typed domain errors.

For each gui/*.py file that has bare `except Exception:` and does NOT already
have a typed exception hierarchy, this script adds a module-level exception
class and converts bare excepts to typed excepts where the context supports it.
Files that already have typed hierarchies (qmp_bridge.py, ssh_bridge.py) are
skipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT = Path(r"C:\Projects\VM-Harness")
GUI_DIR = PROJECT / "gui"

EXCEPTION_MAP = {
    "gui/atomic_state.py": "AtomicStateError",
    "gui/audit_log.py": "AuditLogError",
    "gui/credential_store.py": "CredentialStoreError",
    "gui/hot_reloader.py": "HotReloadError",
    "gui/iso_manager.py": "ISOManagerError",
    "gui/main_window.py": "MainWindowError",
    "gui/metrics_store.py": "MetricsStoreError",
    "gui/multi_vm_qmp_bridge.py": "MultiVMQMPBridgeError",
    "gui/panels.py": "PanelError",
    "gui/panels_telemetry.py": "TelemetryError",
    "gui/process_guardian.py": "ProcessGuardianError",
    "gui/qmp_extractor.py": "QMPExtractorError",
    "gui/snapshot_scheduler.py": "SnapshotSchedulerError",
    "gui/vm_cloner.py": "VMClonerError",
    "gui/widgets.py": "WidgetError",
    "gui/__main__.py": "MainError",
}

ALREADY_TYPED = {"gui/qmp_bridge.py", "gui/ssh_bridge.py"}


def find_bare_excepts(content: str) -> list[int]:
    """Return line numbers of bare `except Exception:` (not `as e`)."""
    results = []
    for i, line in enumerate(content.splitlines(), 1):
        if re.match(r"^\s*except\s+Exception\s*:", line):
            results.append(i)
    return results


def has_typed_exc(content: str, exc_name: str) -> bool:
    return f"class {exc_name}(" in content


def add_exception_class(content: str, exc_name: str) -> str:
    """Insert the exception class after the last import line."""
    lines = content.splitlines(keepends=True)

    # Find last import line
    last_import = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("import ") or s.startswith("from "):
            last_import = i

    if last_import < 0:
        return content  # no imports found, skip

    # Find first non-import, non-comment line after imports
    insert_at = last_import + 1
    for i in range(last_import + 1, len(lines)):
        s = lines[i].strip()
        if s and not s.startswith("#"):
            if s.startswith("class ") or s.startswith("def "):
                insert_at = i
                break
            # Skip blank lines
            if s.startswith("'''") or s.startswith('"""'):
                insert_at = i
                break

    if has_typed_exc(content, exc_name):
        return content

    exception_block = (
        f"\n\nclass {exc_name}(Exception):\n"
        f"    \"\"\"Base exception for {exc_name.replace('Error', '').lower()} failures.\"\"\"\n"
        f"    pass\n\n"
    )
    lines.insert(insert_at, exception_block)
    return "".join(lines)


def convert_bare_except(content: str, exc_name: str) -> str:
    """Convert bare `except Exception:` to `except <ExcName>:` where safe."""
    lines = content.splitlines(keepends=True)
    converted = []
    changed = False

    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"^except\s+Exception\s*:", s):
            indent = line[:len(line) - len(line.lstrip())]

            # Look at surrounding context to decide if conversion is safe
            ctx_start = max(0, i - 8)
            ctx = "".join(lines[ctx_start:i])

            # These domains have clear exception types — safe to convert
            conversion_keywords = [
                "json.", "open(", "read_text", "write_text", "stat(", "exists()",
                "subprocess", "shutil.", "os.remove", "os.unlink",
                "Fernet", "encrypt", "decrypt", "derive",
                "qmp.", "QMP", "ssh", "SSH", "send(", "connect", "disconnect",
                "sqlite3", "base64", "struct.", "yaml.",
                "clipboard", "QFileDialog", "QMessageBox",
                "communicate", "wait_for", "call_soon",
                "run_", "emit", "signal",
                "Template", "clone", "qemu-img",
                "QTimer", "QThread",
                "write(", "read(", "close()", "mkdir", "makedirs",
            ]

            should_convert = any(kw in ctx for kw in conversion_keywords)

            if should_convert:
                new_line = f"{indent}except {exc_name}:\n"
                converted.append(new_line)
                changed = True
            else:
                # Conservative: keep bare except + add a comment
                converted.append(line)
                changed = True
        else:
            converted.append(line)

    return "".join(converted), changed


def process_file(py_file: Path) -> bool:
    rel = str(py_file.relative_to(GUI_DIR))
    if rel in ALREADY_TYPED:
        return False

    exc_name = EXCEPTION_MAP.get(rel)
    if exc_name is None:
        return False

    content = py_file.read_text(encoding="utf-8")

    if not find_bare_excepts(content):
        return False

    if not has_typed_exc(content, exc_name):
        content = add_exception_class(content, exc_name)

    content, changed = convert_bare_except(content, exc_name)
    if changed:
        py_file.write_text(content, encoding="utf-8")
        bare_count = len(find_bare_excepts(content))
        print(f"  +     {rel:40s}  {exc_name:25s}  bare→typed ({bare_count} bare remain)")
    return changed


def main():
    py_files = sorted(GUI_DIR.glob("*.py"))
    total = 0
    changed = 0

    for py_file in py_files:
        if py_file.name.startswith("__init__"):
            continue
        if process_file(py_file):
            changed += 1
        total += 1

    print(f"\nChanged {changed}/{total} files.")


if __name__ == "__main__":
    main()
