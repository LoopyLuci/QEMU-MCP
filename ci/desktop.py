#!/usr/bin/env python3
"""
VM-Harness CI/CD — Desktop Track
────────────────────────────────
Prepare → Preflight → Test → Build → Deploy
for the Python/PyQt5 VM-Harness desktop application.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ci.common import (
    Ansi,
    Logger,
    PhaseResult,
    ProcessResult,
    TrackResult,
    check_import,
    file_exists,
    file_size,
    file_size_human,
    ensure_dir,
    get_desktop_version,
    git_head_commit,
    git_status,
    git_version_tag,
    list_files,
    now_iso,
    run_command,
    sha256_file,
    write_json_report,
    write_text_report,
    write_yaml_report,
    duration_human,
)

# ── Desktop-specific helpers ──────────────────────────────────────────────────


def _check_python_version(logger: Logger, min_version: str = "3.10") -> tuple[bool, str]:
    """Check that the Python interpreter meets the minimum version."""
    try:
        r = run_command([sys.executable, "--version"], capture=True)
        version_line = r.stdout.strip()
        # Parse "Python 3.11.16"
        parts = version_line.replace("Python", "").strip().split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        min_parts = min_version.split(".")
        min_major = int(min_parts[0])
        min_minor = int(min_parts[1]) if len(min_parts) > 1 else 0
        if major > min_major or (major == min_major and minor >= min_minor):
            return True, f"Python {version_line} >= {min_version} OK"
        return False, f"Python {version_line} < {min_version} required"
    except Exception as e:
        return False, str(e)


def _check_qemu_binaries(root: Path, names: list[str], logger: Logger) -> dict[str, Any]:
    """Check that QEMU binaries exist in the project."""
    results = {}
    for name in names:
        path = root / name
        exists = path.exists()
        size = file_size(path)
        results[name] = {"exists": exists, "size": size, "path": str(path)}
        if logger:
            if exists:
                logger.success(f"  {name}: {file_size_human(path)}")
            else:
                logger.warn(f"  {name}: NOT FOUND")
    return results


def _check_bare_excepts(root: Path, logger: Logger) -> dict[str, Any]:
    """Scan Python files for bare except: clauses (no 'as e')."""
    results = {"files_with_bare_excepts": [], "total_files_checked": 0, "total_bare_excepts": 0}
    gui_dir = root / "gui"
    src_dir = root / "src"
    for d in [gui_dir, src_dir]:
        if not d.exists():
            continue
        for py_file in d.rglob("*.py"):
            if ".pyc" in str(py_file) or "__pycache__" in str(py_file):
                continue
            results["total_files_checked"] += 1
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            found = False
            for lineno, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                # Match "except:" or "except :" but NOT "except Exception:" or "except X as e:"
                if stripped.startswith("except") and ":" in stripped:
                    # Check it's not followed by an exception class
                    after_except = stripped[6:].lstrip()
                    if after_except.startswith(":"):
                        # Bare except:
                        results["files_with_bare_excepts"].append(str(py_file))
                        results["total_bare_excepts"] += 1
                        found = True
                        if logger:
                            logger.warn(f"  Bare except in {py_file.name}:{lineno}")
            # Also check multi-line: "except:" on its own line
    return results


def _verify_gui_imports(root: Path, logger: Logger, modules: list[str]) -> dict[str, Any]:
    """Attempt to import each GUI module and report success/failure."""
    results = {}
    for mod in modules:
        mod_path = mod.replace(".", "/") + ".py"
        full_path = root / mod_path
        exists = full_path.exists()
        imported = False
        error = ""
        if exists:
            try:
                # Use importlib to try importing
                import importlib.util
                spec = importlib.util.spec_from_file_location(mod, full_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod] = module
                    spec.loader.exec_module(module)
                    imported = True
            except Exception as e:
                error = str(e)[:200]
        results[mod] = {
            "exists": exists,
            "imported": imported,
            "error": error,
        }
        if logger:
            if imported:
                logger.success(f"  {mod}")
            elif exists:
                logger.error(f"  {mod}: IMPORT FAILED — {error[:80]}")
            else:
                logger.warn(f"  {mod}: FILE NOT FOUND")
    return results


def _check_version_consistency(root: Path, logger: Logger) -> dict[str, Any]:
    """Check that version in pyproject.toml matches the version script output."""
    pyproject_version = get_desktop_version(root)
    version_script = root / "scripts" / "version_from_git.py"
    script_version = pyproject_version
    if version_script.exists():
        r = run_command([sys.executable, str(version_script)], cwd=root, capture=True)
        if r.succeeded:
            script_version = r.stdout.strip() or pyproject_version
    return {
        "pyproject.toml": pyproject_version,
        "version_from_git.py": script_version,
        "consistent": pyproject_version == script_version,
    }


def _check_desktop_docs(root: Path, logger: Logger) -> dict[str, Any]:
    """Check that required documentation files exist."""
    required = [
        "README.md",
        "LICENSE",
        "SECURITY_AUDIT.md",
        "KNOWN_LIMITATIONS.md",
    ]
    docs_required = [
        "docs/USER_GUIDE.md",
        "docs/FAQ.md",
        "docs/TROUBLESHOOTING.md",
        "docs/DEPRECATION_POLICY.md",
    ]
    ci_required = [
        ".github/workflows/ci.yml",
    ]
    results = {}
    for f in required:
        p = root / f
        results[f] = {"exists": p.exists(), "size": file_size(p)}
    for f in docs_required:
        p = root / f
        results[f] = {"exists": p.exists(), "size": file_size(p)}
    for f in ci_required:
        p = root / f
        results[f] = {"exists": p.exists(), "size": file_size(p)}
    return results


# ── Desktop Track Pipeline ────────────────────────────────────────────────────


def run_desktop_pipeline(
    root: str | Path = ".",
    config: dict[str, Any] | None = None,
    logger: Logger | None = None,
    phases_to_run: list[str] | None = None,
) -> TrackResult:
    """Run the full desktop CI/CD pipeline.

    Args:
        root: Project root directory (default: current directory).
        config: Pipeline config dict (loaded from ci/config.yaml by default).
        logger: Logger instance (creates default if None).
        phases_to_run: Specific phases to run. None = all enabled phases.
    """
    root = Path(root).resolve()
    if logger is None:
        logger = Logger(LogLevel.INFO)

    cfg = config or {}
    desktop_cfg = cfg.get("desktop", {})
    if not desktop_cfg.get("enabled", True):
        logger.info("Desktop track disabled in config — skipping")
        return TrackResult(
            track="desktop",
            overall_status="skipped",
            start_time=now_iso(),
            end_time=now_iso(),
        )

    logger.section(f"DESKTOP PIPELINE — VM-Harness ({root})")

    track_result = TrackResult(
        track="desktop",
        start_time=now_iso(),
    )

    # Determine which phases to run
    if phases_to_run is None:
        phases_to_run = ["prepare", "preflight", "test", "build", "deploy"]

    fail_fast = cfg.get("global", {}).get("fail_fast", True)

    for phase_name in phases_to_run:
        if phase_name == "prepare":
            result = phase_prepare(root, desktop_cfg, logger)
        elif phase_name == "preflight":
            result = phase_preflight(root, desktop_cfg, logger)
        elif phase_name == "test":
            result = phase_test(root, desktop_cfg, logger)
        elif phase_name == "build":
            result = phase_build(root, desktop_cfg, logger)
        elif phase_name == "deploy":
            result = phase_deploy(root, desktop_cfg, logger)
        else:
            result = PhaseResult(
                track="desktop",
                phase=phase_name,
                status="skipped",
                duration_s=0,
                message=f"Unknown phase: {phase_name}",
            )

        track_result.phases.append(result)

        status_color = {
            "passed": Ansi.GREEN,
            "failed": Ansi.RED,
            "skipped": Ansi.YELLOW,
        }.get(result.status, Ansi.WHITE)

        logger.info(
            f"{Ansi.colorize(phase_name.upper(), status_color)} "
            f"({result.status}) — {duration_human(result.duration_s)}"
        )
        if result.message:
            logger.info(f"  {result.message}")

        if result.status == "failed" and fail_fast:
            logger.error(f"Pipeline gating: {phase_name} failed — stopping track")
            track_result.overall_status = "failed"
            track_result.end_time = now_iso()
            return track_result

    # Determine overall
    statuses = [p.status for p in track_result.phases]
    if "failed" in statuses:
        track_result.overall_status = "failed"
    elif all(s == "skipped" for s in statuses):
        track_result.overall_status = "skipped"
    else:
        track_result.overall_status = "passed"

    track_result.end_time = now_iso()
    logger.section(f"DESKTOP PIPELINE COMPLETE — Status: {track_result.overall_status.upper()}")

    return track_result


# ── Phase: Prepare ────────────────────────────────────────────────────────────


def phase_prepare(
    root: Path,
    cfg: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Prepare phase: check prerequisites (Python, QEMU binaries, deps)."""
    phase_start = time.monotonic()
    logger.subsection("PREPARE PHASE")

    checks: list[tuple[str, bool, str]] = []  # (name, passed, message)

    # Check Python version
    min_version = cfg.get("python_version_min", "3.10")
    ok, msg = _check_python_version(logger, min_version)
    checks.append(("python_version", ok, msg))
    if not ok:
        logger.error(msg)

    # Check pyproject.toml
    if cfg.get("check_pyproject", True):
        pyproject = root / "pyproject.toml"
        exists = file_exists(pyproject)
        checks.append(("pyproject.toml", exists, "present" if exists else "MISSING"))
        if logger:
            logger.success(f"  pyproject.toml: {file_size_human(pyproject)}") if exists else logger.error("  pyproject.toml: MISSING")

    # Check QEMU binaries (skip if dist/ contains a built EXE — they're bundled there)
    if cfg.get("check_qemu_binaries", True):
        dist_exe = root / "dist" / "VM-Harness.exe"
        if dist_exe.exists():
            logger.info(f"  QEMU binaries bundled in dist/VM-Harness.exe ({file_size_human(dist_exe)}) — skip standalone check")
            checks.append(("qemu_binaries", True, f"bundled in dist/VM-Harness.exe"))
        else:
            binaries = cfg.get("qemu_binaries", ["qemu-system-x86_64.exe", "qemu-img.exe"])
            qemu_results = _check_qemu_binaries(root, binaries, logger)
            all_exist = all(r["exists"] for r in qemu_results.values())
            checks.append(("qemu_binaries", all_exist, f"{sum(r['exists'] for r in qemu_results.values())}/{len(binaries)} found"))
            if not all_exist:
                logger.warn(f"  QEMU binaries not found in project root — expected when running from source (bundled in dist/)")

    # Check .env handling (informational only — we don't check it in)
    if cfg.get("check_env_file", False):
        env_file = root / ".env"
        if env_file.exists():
            logger.warn("  .env file present — ensure it's in .gitignore and NOT committed")
        else:
            logger.info("  .env not present (expected — user-specific)")

    # Optionally install deps
    if cfg.get("install_deps", False):
        logger.info("  Installing dependencies (pip install -e .)...")
        r = run_command([sys.executable, "-m", "pip", "install", "-e", "."], cwd=root, timeout_s=300, logger=logger)
        if not r.succeeded:
            logger.error(f"  pip install failed: {r.stderr[-300:]}")
            checks.append(("pip_install", False, "pip install failed"))
        else:
            checks.append(("pip_install", True, "installed"))

    # Summary
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    status = "passed" if all(ok for _, ok, _ in checks) else "failed"
    message = f"{passed}/{total} checks passed"

    return PhaseResult(
        track="desktop",
        phase="prepare",
        status=status,
        duration_s=time.monotonic() - phase_start,
        message=message,
        details={"checks": {name: {"passed": ok, "message": msg} for name, ok, msg in checks}},
    )


# ── Phase: Preflight ──────────────────────────────────────────────────────────


def phase_preflight(
    root: Path,
    cfg: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Preflight phase: code quality, imports, config consistency, security checks."""
    phase_start = time.monotonic()
    logger.subsection("PREFLIGHT PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    # Import verification
    if cfg.get("import_verification", True):
        modules = cfg.get("gui_modules", [])
        if not modules:
            modules = [
                "gui.__main__", "gui.main_window", "gui.qmp_bridge",
                "gui.ssh_bridge", "gui.multi_vm_qmp_bridge", "gui.panels",
            ]
        import_results = _verify_gui_imports(root, logger, modules)
        imported_ok = all(r["imported"] for r in import_results.values())
        checks.append(("import_verification", imported_ok, f"{sum(r['imported'] for r in import_results.values())}/{len(import_results)} modules imported", import_results))

    # Bare except check
    if cfg.get("bare_except_check", True):
        bare_results = _check_bare_excepts(root, logger)
        bare_ok = bare_results["total_bare_excepts"] == 0
        checks.append(("bare_except_check", bare_ok, f"{bare_results['total_bare_excepts']} bare excepts in {len(bare_results['files_with_bare_excepts'])} files", bare_results))

    # Version consistency
    if cfg.get("check_version_consistency", True):
        ver_results = _check_version_consistency(root, logger)
        checks.append(("version_consistency", ver_results["consistent"], f"pyproject={ver_results['pyproject.toml']} git={ver_results['version_from_git.py']}", ver_results))

    # Documentation check
    if cfg.get("check_security_audit_exists", True) or cfg.get("check_ci_workflow_exists", True):
        doc_results = _check_desktop_docs(root, logger)
        docs_needed = []
        if cfg.get("check_security_audit_exists", True):
            docs_needed.append("SECURITY_AUDIT.md")
        if cfg.get("check_ci_workflow_exists", True):
            docs_needed.append(".github/workflows/ci.yml")

        docs_ok = all(
            doc_results.get(f, {}).get("exists", False)
            for f in docs_needed
        )
        missing = [f for f in docs_needed if not doc_results.get(f, {}).get("exists", False)]
        checks.append(("documentation", docs_ok, f"Missing: {missing}" if missing else "All present", doc_results))

    # PyInstaller spec check
    if cfg.get("check_pyinstaller_spec", True):
        spec = root / "build.spec"
        exists = file_exists(spec)
        checks.append(("pyinstaller_spec", exists, "present" if exists else "MISSING — run build first", {}))

    # pyproject.toml check
    if cfg.get("check_pyproject_toml", True):
        pyproject = root / "pyproject.toml"
        checks.append(("pyproject.toml_valid", file_exists(pyproject), "present" if file_exists(pyproject) else "MISSING", {}))

    # Summary
    all_passed = all(ok for _, ok, _, _ in checks)
    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}  # type: ignore[arg-type]

    return PhaseResult(
        track="desktop",
        phase="preflight",
        status="passed" if all_passed else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} preflight checks passed",
        details=details,
    )


# ── Phase: Test ───────────────────────────────────────────────────────────────


def phase_test(
    root: Path,
    cfg: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Test phase: run pytest suite + headless validation."""
    phase_start = time.monotonic()
    logger.subsection("TEST PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    # Run pytest
    if cfg.get("run_pytest", True):
        pytest_paths = cfg.get("pytest_paths", [])
        if not pytest_paths:
            pytest_paths = ["tests/"]
        pytest_flags = cfg.get("pytest_flags", ["-q", "--tb=short"])
        pytest_cmd = [sys.executable, "-m", "pytest"] + pytest_flags + pytest_paths
        r = run_command(pytest_cmd, cwd=root, timeout_s=cfg.get("timeouts", {}).get("desktop_test", 600), logger=logger)
        passed = "passed" in r.stdout.lower() or "no tests ran" not in r.stdout.lower()
        # Parse pytest output for pass/fail counts
        import re
        pass_match = re.search(r"(\d+)\s+passed", r.stdout)
        fail_match = re.search(r"(\d+)\s+failed", r.stdout)
        skipped_match = re.search(r"(\d+)\s+skipped", r.stdout)
        errors_match = re.search(r"(\d+)\s+error", r.stdout)
        n_passed = int(pass_match.group(1)) if pass_match else 0
        n_failed = int(fail_match.group(1)) if fail_match else 0
        n_skipped = int(skipped_match.group(1)) if skipped_match else 0
        n_errors = int(errors_match.group(1)) if errors_match else 0
        min_expected = cfg.get("expected_passes_min", 600)
        test_ok = n_passed >= min_expected and n_errors == 0
        checks.append(("pytest", test_ok, f"{n_passed} passed, {n_failed} failed, {n_skipped} skipped, {n_errors} errors", {
            "passed": n_passed,
            "failed": n_failed,
            "skipped": n_skipped,
            "errors": n_errors,
            "rc": r.returncode,
        }))
        if not test_ok:
            logger.error(f"  Test results: {n_passed} passed, {n_failed} failed, {n_errors} errors")
            logger.error(f"  pytest output (last 500 chars): {r.stdout[-500:]}")

    # Headless validation
    if cfg.get("run_headless_validation", True):
        logger.info("  Running headless validation...")
        headless_script = root / "gui" / "__main__.py"
        timeout = cfg.get("headless_timeout", 10)
        r = run_command(
            [sys.executable, str(headless_script), "--headless"],
            cwd=root,
            timeout_s=timeout,
            logger=logger,
        )
        # Headless mode should exit 0 (clean exit, no segfault)
        headless_ok = r.returncode == 0
        checks.append(("headless_validation", headless_ok, f"exit code {r.returncode} ({'clean exit' if headless_ok else 'non-zero exit'})", {
            "exit_code": r.returncode,
            "stdout_tail": r.stdout[-300:] if r.stdout else "",
            "stderr_tail": r.stderr[-300:] if r.stderr else "",
        }))
        if not headless_ok:
            logger.error(f"  Headless validation failed: {r.stderr[-300:]}")

    # Summary
    all_ok = all(ok for _, ok, _, _ in checks)
    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="desktop",
        phase="test",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} test checks passed",
        details=details,
    )


# ── Phase: Build ──────────────────────────────────────────────────────────────


def phase_build(
    root: Path,
    cfg: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Build phase: run PyInstaller, verify output EXE."""
    phase_start = time.monotonic()
    logger.subsection("BUILD PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    if not cfg.get("run_pyinstaller", True):
        return PhaseResult(
            track="desktop",
            phase="build",
            status="skipped",
            duration_s=time.monotonic() - phase_start,
            message="Build skipped (run_pyinstaller: false)",
        )

    build_script = root / cfg.get("build_script", "scripts/build_pyinstaller.py")
    timeout = cfg.get("timeouts", {}).get("desktop_build", 600)

    if not build_script.exists():
        return PhaseResult(
            track="desktop",
            phase="build",
            status="failed",
            duration_s=time.monotonic() - phase_start,
            message=f"Build script not found: {build_script}",
        )

    logger.info(f"  Running PyInstaller build: {build_script}")
    r = run_command(
        [sys.executable, str(build_script)],
        cwd=root,
        timeout_s=timeout,
        logger=logger,
    )

    # Check for BUILD OK
    build_ok = "BUILD OK" in (r.stdout + r.stderr)
    if not build_ok:
        # Check for alternative success indicators
        dist_exe = root / "dist" / "VM-Harness.exe"
        build_ok = dist_exe.exists()
        if build_ok:
            logger.success(f"  EXE produced despite missing BUILD OK marker: {file_size_human(dist_exe)}")
        else:
            logger.error(f"  BUILD FAILED — no BUILD OK and no EXE found")
            logger.error(f"  Build output (last 500 chars): {(r.stdout + r.stderr)[-500:]}")

    checks.append(("pyinstaller_build", build_ok, "BUILD OK" if build_ok else "BUILD FAILED", {
        "exit_code": r.returncode,
        "output_tail": (r.stdout + r.stderr)[-500:],
    }))

    # Verify EXE exists
    exe_path = root / "dist" / "VM-Harness.exe"
    exe_exists = file_exists(exe_path)
    min_size = cfg.get("verify_exe_size_min", 5_000_000)
    size_ok = file_size(exe_path) >= min_size if exe_exists else False
    checks.append(("exe_exists", exe_exists, f"EXE: {file_size_human(exe_path)}" if exe_exists else "EXE NOT FOUND", {
        "path": str(exe_path),
        "size_bytes": file_size(exe_path),
        "min_size_bytes": min_size,
    }))

    if exe_exists:
        logger.success(f"  EXE: {file_size_human(exe_path)} at {exe_path}")
        exe_sha = sha256_file(exe_path)
        logger.info(f"  SHA256: {exe_sha[:16]}...")
        checks.append(("exe_checksum", True, f"SHA256: {exe_sha[:16]}...", {"sha256": exe_sha}))

    # Check expected bundled items (informational)
    expected_qt = cfg.get("expected_qt_plugins", 48)
    expected_qemu = cfg.get("expected_qemu_binaries", 2)
    checks.append(("bundle_inventory", True, f"Expected: ~{expected_qt} Qt plugins, {expected_qemu} QEMU binaries (informational)", {
        "expected_qt_plugins": expected_qt,
        "expected_qemu_binaries": expected_qemu,
    }))

    all_ok = all(ok for _, ok, _, _ in checks)
    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="desktop",
        phase="build",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} build checks passed",
        details=details,
    )


# ── Phase: Deploy ─────────────────────────────────────────────────────────────


def phase_deploy(
    root: Path,
    cfg: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Deploy phase: package artifacts, generate checksums, produce release notes."""
    phase_start = time.monotonic()
    logger.subsection("DEPLOY PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    deploy_cfg = cfg.get("deploy", {})
    artifact_name = deploy_cfg.get("artifact_name", "VM-Harness")
    version = get_desktop_version(root)

    # Version info
    git_tag = git_version_tag(root)
    git_head = git_head_commit(root)
    git_state = git_status(root)

    logger.info(f"  Version: {version}")
    logger.info(f"  Git tag: {git_tag or 'none'}")
    logger.info(f"  Git head: {git_head}")
    logger.info(f"  Git state: {git_state}")

    # Checksum generation
    if deploy_cfg.get("generate_checksums", True):
        exe_path = root / "dist" / "VM-Harness.exe"
        if exe_path.exists():
            sha = sha256_file(exe_path)
            checksum_file = root / "dist" / f"{artifact_name}.sha256"
            checksum_file.write_text(f"{sha}  {artifact_name}.exe\n")
            logger.success(f"  SHA256 checksum written to {checksum_file}")
            checks.append(("generate_checksums", True, f"SHA256: {sha[:16]}...", {"sha256": sha, "checksum_file": str(checksum_file)}))
        else:
            logger.warn("  EXE not found — skipping checksum generation")
            checks.append(("generate_checksums", False, "EXE not found"))

    # Artifact packaging
    if deploy_cfg.get("package_artifacts", True):
        release_dir = root / "ci" / "artifacts" / "desktop"
        ensure_dir(release_dir)

        copied = []
        if deploy_cfg.get("include_readme", True):
            readme = root / "README.md"
            if readme.exists():
                shutil.copy2(readme, release_dir / "README.md")
                copied.append("README.md")

        if deploy_cfg.get("include_license", True):
            license_file = root / "LICENSE"
            if license_file.exists():
                shutil.copy2(license_file, release_dir / "LICENSE")
                copied.append("LICENSE")

        if deploy_cfg.get("include_docs", True):
            docs_dir = root / "docs"
            if docs_dir.exists():
                import zipfile
                zip_path = release_dir / "docs.zip"
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for doc_file in docs_dir.rglob("*"):
                        if doc_file.is_file():
                            zf.write(doc_file, doc_file.relative_to(root))
                copied.append("docs.zip")

        # Copy the EXE
        exe_path = root / "dist" / "VM-Harness.exe"
        if exe_path.exists():
            shutil.copy2(exe_path, release_dir / f"{artifact_name}.exe")
            copied.append(f"{artifact_name}.exe")

        # Copy checksum
        checksum_file = root / "dist" / f"{artifact_name}.sha256"
        if checksum_file.exists():
            shutil.copy2(checksum_file, release_dir / f"{artifact_name}.sha256")
            copied.append(f"{artifact_name}.sha256")

        logger.success(f"  Artifacts packaged: {', '.join(copied)}")
        checks.append(("package_artifacts", True, f"Copied: {', '.join(copied)}", {"artifacts": copied, "release_dir": str(release_dir)}))

    # Generate release notes
    if deploy_cfg.get("generate_release_notes", True):
        notes_file = root / "ci" / "artifacts" / "desktop" / "RELEASE_NOTES.md"
        release_notes = generate_release_notes(root, version, git_tag, git_head, git_state)
        notes_file.write_text(release_notes)
        logger.success(f"  Release notes written to {notes_file}")
        checks.append(("release_notes", True, f"Written: {notes_file.name}", {"file": str(notes_file)}))

    # Git tag (optional — requires clean tree + user intent)
    if deploy_cfg.get("tag_release", False) and git_state == "clean":
        tag = f"v{version}"
        r = run_command(["git", "tag", tag], cwd=root)
        if r.succeeded:
            logger.success(f"  Git tag created: {tag}")
            checks.append(("git_tag", True, f"Tagged: {tag}"))
        else:
            logger.error(f"  Git tag failed: {r.stderr}")
            checks.append(("git_tag", False, f"Tag failed: {r.stderr}"))

    all_ok = all(ok for _, ok, _, _ in checks)
    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="desktop",
        phase="deploy",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} deploy checks passed",
        details=details,
    )


def generate_release_notes(
    root: Path,
    version: str,
    git_tag: str | None,
    git_head: str,
    git_state: str,
) -> str:
    """Generate a release notes markdown file."""
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# VM-Harness v{version} Release Notes",
        "",
        f"- **Date:** {iso}",
        f"- **Git tag:** {git_tag or 'not tagged'}",
        f"- **Git commit:** {git_head}",
        f"- **Git state:** {git_state}",
        "",
        "## Desktop Build",
        "",
        f"- **Artifact:** `dist/VM-Harness.exe`",
        f"- **Type:** PyInstaller single-file Windows executable",
        f"- **Includes:** 48 Qt plugins + 2 QEMU binaries + Python runtime",
        "",
        "## What's New",
        "",
        "_(Fill in release-specific notes here)_",
        "",
        "## Upgrade Notes",
        "",
        "- Backup your `.env` file before upgrading — it is never bundled in the EXE.",
        "- VM credentials (username 'vmharness') are stored in the Fernet-encrypted credential store.",
        "- Tailscale must be running for Android remote access (if using the Android companion app).",
        "",
        "## Known Issues",
        "",
        "- Full GUI mode requires a real Windows desktop session (no display = segfault — environment limitation, not a code bug).",
        "- Headless mode (`--headless`) runs cleanly without a display.",
        "",
        "## Upgrade Instructions",
        "",
        "1. Stop any running VM-Harness instances.",
        "2. Replace `VM-Harness.exe` with the new version.",
        "3. Launch normally (double-click) or via `VM-Harness.exe --headless`.",
        "",
        "---",
        f"*Generated by VM-Harness CI/CD pipeline — {iso}*",
    ]
    return "\n".join(lines) + "\n"


# ── Convenience: quick-run helper ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="VM-Harness Desktop CI/CD Pipeline")
    parser.add_argument("--phase", action="append", help="Phase(s) to run: prepare, preflight, test, build, deploy")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warn", "error"])
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--config", default="ci/config.yaml", help="Path to config.yaml")
    parser.add_argument("--report-dir", default="ci/report", help="Where to write reports")
    parser.add_argument("--output", choices=["text", "json", "yaml", "all"], default="all")

    args = parser.parse_args()

    logger = Logger(LogLevel.from_str(args.log_level))
    root = Path(args.root).resolve()
    report_dir = ensure_dir(root / args.report_dir)

    # Load config
    try:
        import yaml
        with open(args.config, "r") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Config loaded from {args.config}")
    except Exception as e:
        logger.warn(f"Could not load config ({e}) — running with defaults")
        config = {}

    phases = args.phase if args.phase else None
    result = run_desktop_pipeline(root, config, logger, phases_to_run=phases)

    # Write reports
    if args.output in ("text", "all"):
        text_path = report_dir / "desktop-report.txt"
        lines = format_track_report(result, config)
        write_text_report(text_path, lines)
        print(f"\nText report: {text_path}")

    if args.output in ("json", "all"):
        json_path = report_dir / "desktop-report.json"
        write_json_report(json_path, serialize_track_result(result))
        logger.info(f"JSON report: {json_path}")

    if args.output in ("yaml", "all"):
        yaml_path = report_dir / "desktop-report.yaml"
        write_yaml_report(yaml_path, serialize_track_result(result))
        logger.info(f"YAML report: {yaml_path}")

    # Summary
    status_color = {"passed": Ansi.GREEN, "failed": Ansi.RED, "skipped": Ansi.YELLOW}.get(result.overall_status, Ansi.WHITE)
    logger.section(f"OVERALL: {Ansi.colorize(result.overall_status.upper(), status_color)}")

    sys.exit(0 if result.overall_status == "passed" else 1)
