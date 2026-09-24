#!/usr/bin/env python3
"""Comprehensive type hints audit and completion script.

Scans all Python files in src/vm_harness/, gui/, and tests/ for public methods
missing type hints, adds appropriate annotations, and verifies with mypy.

Focus areas:
1. Backend classes (ContainerBackend, HypervisorBackend and all sub-backends)
2. Adapter classes (AsyncAdapter and all sub-adapters)
3. Panel classes (all 34 panels)
4. Dialog classes
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "vm_harness"
GUI_DIR = PROJECT_ROOT / "gui"
TESTS_DIR = PROJECT_ROOT / "tests"

# Type mappings for common parameter names
PARAM_TYPE_MAP: Dict[str, str] = {
    # Common Qt params
    "parent": "QWidget",
    "event": "QEvent",
    "bridge": "QMPBridge",
    "ssh_bridge": "SSHBridge",
    "qmp_bridge": "QMPBridge",
    "server": "QThread",
    "manager": "VMManager",
    "app": "QApplication",
    "qtbot": "QtBot",
    "monkeypatch": "MonkeyPatch",
    "tmp_path": "Path",
    # Backend params
    "config": "dict[str, Any]",
    "config_obj": "Any",
    # Method params
    "container_id": "str",
    "container_name": "str",
    "image_name": "str",
    "image_id": "str",
    "command": "str",
    "commands": "list[str]",
    "data": "str",
    "data_bytes": "bytes",
    "namespace": "str",
    "pod_name": "str",
    "node_name": "str",
    "vm_name": "str",
    "snapshot_name": "str",
    "message": "str",
    "text": "str",
    "title": "str",
    "name": "str",
    "value": "Any",
    "values": "list[float]",
    "status": "dict[str, Any]",
    "manifest": "dict[str, Any]",
    "kind": "str",
    "mode": "str",
    "mac": "str",
    "password": "str",
    "path": "str",
    "output_path": "str",
    "input_path": "str",
    "iso_path": "str",
    "format": "str",
    "new_name": "str",
    "vm": "str",
    "size_gb": "int",
    "timeout": "int",
    "tail": "int",
    "force": "bool",
    "headless": "bool",
    "connected": "bool",
    "live": "bool",
    "include_memory": "bool",
    "description": "str",
    "max_bytes": "int",
    "new_size_gb": "int",
    "max_ram_mb": "int",
    "max_cpus": "int",
    "cpu_shares": "int",
    "io_bandwidth_mbps": "int",
    "vendor_id": "str",
    "product_id": "str",
    "target_uri": "str",
    "bandwidth_mbps": "int",
    "interval_s": "float",
    "network": "VMNetwork",
    "metrics_store": "MetricsStore",
    "editor": "NetworkConfigEditor",
    "editor_widget": "NetworkConfigEditor",
}

RETURN_TYPE_MAP: Dict[str, str] = {
    "list_containers": "list[dict[str, Any]]",
    "get_container": "Any",
    "get_stats": "dict[str, Any]",
    "get_logs": "str",
    "create_container": "Any",
    "start_container": "None",
    "stop_container": "None",
    "restart_container": "None",
    "remove_container": "None",
    "inspect_container": "dict[str, Any]",
    "list_images": "list[dict[str, Any]]",
    "pull_image": "str",
    "remove_image": "None",
    "exec_command": "str",
    "list_pods": "list[dict[str, Any]]",
    "list_all_pods": "list[dict[str, Any]]",
    "list_services": "list[dict[str, Any]]",
    "list_deployments": "list[dict[str, Any]]",
    "list_nodes": "list[dict[str, Any]]",
    "list_namespaces": "list[str]",
    "apply_manifest": "Any",
    "delete_resource": "None",
    "exec_in_pod": "str",
    "get_pod_logs": "str",
    "list_vms": "list[dict[str, Any]]",
    "create_vm": "str",
    "destroy_vm": "None",
    "start_vm": "None",
    "stop_vm": "None",
    "get_status": "str",
    "pause_vm": "None",
    "resume_vm": "None",
    "reset_vm": "None",
    "query_status": "dict[str, Any]",
    "power_on": "None",
    "power_off": "None",
    "suspend": "None",
    "reset": "None",
    "create_snapshot": "None",
    "list_snapshots": "list[Any]",
    "refresh": "None",
    "add_activity": "None",
    "set_qmp_bridge": "None",
    "set_ssh_bridge": "None",
    "set_server": "None",
    "set_metrics_store": "None",
    "set_config": "None",
    "set_mode": "None",
    "set_adapter": "None",
    "set_mac": "None",
    "set_bandwidth": "None",
    "set_port_forwards": "None",
    "set_active_vm": "None",
    "set_multi_qmp_bridge": "None",
    "set_manager": "None",
    "switch_to_vm": "None",
    "set_result": "None",
    "load_credential": "dict[str, Any]",
    "add_value": "None",
    "cancel": "None",
    "run": "None",
    "start_pull": "None",
    "exec_": "int",
    "closeEvent": "None",
    "reject": "None",
    "showEvent": "None",
    "hideEvent": "None",
    "paintEvent": "None",
    "mousePressEvent": "None",
}


def find_python_files() -> List[Path]:
    """Find all Python files in target directories."""
    files = []
    for base in [SRC_DIR, GUI_DIR, TESTS_DIR]:
        if base.exists():
            files.extend(base.rglob("*.py"))
    return sorted(files)


def should_skip_method(class_name: str, method_name: str, filepath: Path) -> bool:
    """Check if a method should be skipped (dunder, private, etc.)."""
    if method_name.startswith("_") and not method_name.startswith("__"):
        # Skip private methods but not dunder methods like __init__
        return False  # We'll include __init__ overrides that are public
    if method_name in ("__init__", "__new__", "__del__", "__repr__", "__str__",
                        "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
                        "__hash__", "__bool__", "__len__", "__iter__", "__next__",
                        "__enter__", "__exit__", "__aenter__", "__aexit__",
                        "__getitem__", "__setitem__", "__delitem__",
                        "__contains__", "__call__", "__await__"):
        return True  # Skip dunder methods
    return False


def get_param_type(param_name: str, class_name: str, method_name: str,
                   filepath: Path, arg_node: ast.arg) -> str:
    """Determine the appropriate type for a parameter."""
    if param_name in PARAM_TYPE_MAP:
        return PARAM_TYPE_MAP[param_name]

    # Check if there's already a partial annotation
    if arg_node.annotation:
        # Already has a type, return existing
        if isinstance(arg_node.annotation, ast.Name):
            return arg_node.annotation.id
        elif isinstance(arg_node.annotation, ast.Subscript):
            return "Any"

    # Context-based inference
    if "filepath" in param_name or "path" in param_name:
        return "str"
    if "timeout" in param_name:
        return "int"
    if "enabled" in param_name or "visible" in param_name or "active" in param_name:
        return "bool"
    if "count" in param_name or "index" in param_name or "size" in param_name:
        return "int"

    return "Any"


def get_return_type(method_name: str, class_name: str, filepath: Path) -> str:
    """Determine the appropriate return type for a method."""
    if method_name in RETURN_TYPE_MAP:
        return RETURN_TYPE_MAP[method_name]

    # Check for patterns
    if method_name.startswith("get_"):
        return "Any"
    if method_name.startswith("set_"):
        return "None"
    if method_name.startswith("list_"):
        return "list[Any]"
    if method_name.startswith("is_"):
        return "bool"
    if method_name.startswith("has_"):
        return "bool"
    if method_name.startswith("add_"):
        return "None"
    if method_name.startswith("remove_"):
        return "None"
    if method_name.startswith("create_"):
        return "Any"
    if method_name.startswith("on_"):
        return "None"
    if method_name.startswith("show"):
        return "None"
    if method_name.startswith("close"):
        return "None"

    return "None"


def add_type_hints_to_file(filepath: Path) -> int:
    """Add type hints to public methods in a file. Returns number of methods updated."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return 0

    lines = source.split("\n")
    changes: List[Tuple[int, str, str]] = []  # (line_num, old_text, new_text)

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        class_name = node.name

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            method_name = item.name

            if should_skip_method(class_name, method_name, filepath):
                continue

            # Check if method already has full type hints
            has_return = item.returns is not None
            args = item.args
            all_args = args.posonlyargs + args.args + args.kwonlyargs

            missing_params = []
            for arg in all_args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    missing_params.append(arg.arg)

            if has_return and not missing_params:
                continue  # Already fully typed

            # Build the new method signature
            # This is complex to do line-by-line, so we'll reconstruct the signature
            new_sig = build_method_signature(item, missing_params, has_return, filepath)
            old_sig = get_original_signature(lines, item.lineno - 1)

            if new_sig != old_sig:
                changes.append((item.lineno - 1, old_sig, new_sig))

    # Apply changes in reverse order to preserve line numbers
    changes.sort(key=lambda x: x[0], reverse=True)

    for line_num, old_sig, new_sig in changes:
        if old_sig in lines[line_num]:
            lines[line_num] = lines[line_num].replace(old_sig, new_sig, 1)

    if changes:
        new_source = "\n".join(lines)
        filepath.write_text(new_source, encoding="utf-8")

    return len(changes)


def get_original_signature(lines: List[str], start_line: int) -> str:
    """Extract the original method signature from source lines."""
    # Collect lines until we find the closing parenthesis + colon
    sig_lines = []
    paren_depth = 0
    started = False

    for i in range(start_line, min(start_line + 20, len(lines))):
        line = lines[i]
        sig_lines.append(line)

        for ch in line:
            if ch == "(":
                paren_depth += 1
                started = True
            elif ch == ")":
                paren_depth -= 1

        if started and paren_depth == 0:
            # Check if this line or next has the return type + colon
            remaining = line.split(")", 1)
            if len(remaining) > 1:
                after_paren = remaining[1].strip()
                if after_paren.startswith("->") or after_paren.startswith(":"):
                    break
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("->") or next_line.startswith(":"):
                    sig_lines.append(lines[i + 1])
                    break
            break

    return "\n".join(sig_lines)


def build_method_signature(func_node: ast.FunctionDef,
                           missing_params: List[str],
                           has_return: bool,
                           filepath: Path) -> str:
    """Build a new method signature with type hints."""
    args = func_node.args

    # Determine prefix (async or not)
    prefix = "async def" if isinstance(func_node, ast.AsyncFunctionDef) else "def"

    # Build parameter list
    param_parts: List[str] = []

    # positional-only args
    for arg in args.posonlyargs:
        if arg.arg in ("self", "cls"):
            continue
        type_str = get_param_type(arg.arg, "", func_node.name, filepath, arg)
        if arg.annotation is None:
            param_parts.append(f"{arg.arg}: {type_str}")
        else:
            param_parts.append(arg.arg)

    if args.posonlyargs:
        param_parts.append("/")

    # regular args
    for arg in args.args:
        if arg.arg in ("self", "cls"):
            continue
        type_str = get_param_type(arg.arg, "", func_node.name, filepath, arg)
        if arg.annotation is None:
            param_parts.append(f"{arg.arg}: {type_str}")
        else:
            param_parts.append(arg.arg)

    # *args
    if args.vararg:
        if args.vararg.annotation is None:
            param_parts.append(f"*{args.vararg.arg}: Any")
        else:
            param_parts.append(f"*{args.vararg.arg}")

    # keyword-only args
    for arg in args.kwonlyargs:
        type_str = get_param_type(arg.arg, "", func_node.name, filepath, arg)
        if arg.annotation is None:
            # Check if there's a default value
            default_str = ""
            # Find matching default
            param_parts.append(f"{arg.arg}: {type_str}{default_str}")
        else:
            param_parts.append(arg.arg)

    # **kwargs
    if args.kwarg:
        if args.kwarg.annotation is None:
            param_parts.append(f"**{args.kwarg.arg}: Any")
        else:
            param_parts.append(f"**{args.kwarg.arg}")

    # Build return type
    return_type = ""
    if not has_return:
        rt = get_return_type(func_node.name, "", filepath)
        return_type = f" -> {rt}"
    else:
        # Already has return type, extract it
        # We'll keep the existing one
        return_type = ""  # Will be preserved from original

    params_str = ", ".join(param_parts)
    return f"{prefix} {func_node.name}({params_str}){return_type}:"


def run_mypy(paths: List[str]) -> Tuple[bool, str]:
    """Run mypy on the specified paths. Returns (success, output)."""
    cmd = [
        sys.executable, "-m", "mypy",
        "--show-error-codes",
        "--ignore-missing-imports",
        "--no-strict-optional",
        "--check-untyped-defs",
        *paths,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )

    output = result.stdout + result.stderr
    success = result.returncode == 0
    return success, output


def main():
    print("=" * 70)
    print("Type Hints Audit & Completion Script")
    print("=" * 70)

    # Phase 1: Audit
    print("\n[Phase 1] Auditing public methods for missing type hints...")
    all_files = find_python_files()

    total_methods = 0
    methods_needing_hints: Dict[Path, List[Dict]] = {}

    for filepath in all_files:
        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        missing = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_name = node.name

            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                if should_skip_method(class_name, item.name, filepath):
                    continue

                total_methods += 1

                has_return = item.returns is not None
                args = item.args
                all_args = args.posonlyargs + args.args + args.kwonlyargs

                missing_params = []
                for arg in all_args:
                    if arg.arg in ("self", "cls"):
                        continue
                    if arg.annotation is None:
                        missing_params.append(arg.arg)

                if not has_return or missing_params:
                    missing.append({
                        "class": class_name,
                        "method": item.name,
                        "line": item.lineno,
                        "has_return": has_return,
                        "missing_params": missing_params,
                    })

        if missing:
            methods_needing_hints[filepath] = missing

    print(f"  Total public methods audited: {total_methods}")
    print(f"  Files with methods needing hints: {len(methods_needing_hints)}")
    total_missing = sum(len(v) for v in methods_needing_hints.values())
    print(f"  Total methods needing type hints: {total_missing}")

    # Phase 2: Add type hints
    print("\n[Phase 2] Adding type hints...")

    # Focus files only (backend, adapter, panel, dialog)
    focus_patterns = ["backend", "adapter", "panel", "dialog"]
    focus_files = [f for f in methods_needing_hints
                   if any(kw in f.name for kw in focus_patterns)]

    # Also include specific panel files
    panel_files = [f for f in methods_needing_hints
                   if "panels" in f.name.lower()]

    all_target_files = set(focus_files + panel_files)

    total_modified = 0
    for filepath in sorted(all_target_files):
        count = add_type_hints_to_file(filepath)
        if count > 0:
            rel = filepath.relative_to(PROJECT_ROOT)
            print(f"  ✓ {rel}: {count} methods updated")
            total_modified += count

    print(f"\n  Total methods updated: {total_modified}")

    # Phase 3: Verify with mypy
    print("\n[Phase 3] Running mypy verification...")

    # Run mypy on modified files
    modified_paths = [str(f.relative_to(PROJECT_ROOT)) for f in all_target_files]

    # Split into batches to avoid command line length limits
    batch_size = 20
    all_passed = True
    all_output = []

    for i in range(0, len(modified_paths), batch_size):
        batch = modified_paths[i:i + batch_size]
        success, output = run_mypy(batch)
        if not success:
            all_passed = False
            all_output.append(output)
        else:
            all_output.append(f"Batch {i // batch_size + 1}: OK")

    if all_passed:
        print("  ✓ mypy verification passed for all files!")
    else:
        print("  ✗ mypy found issues in some files:")
        for output in all_output:
            if "OK" not in output:
                print(output)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Files scanned: {len(all_files)}")
    print(f"  Public methods found: {total_methods}")
    print(f"  Methods needing type hints: {total_missing}")
    print(f"  Focus files updated: {len(all_target_files)}")
    print(f"  Total methods updated: {total_modified}")
    print(f"  mypy status: {'PASSED' if all_passed else 'ISSUES FOUND'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())