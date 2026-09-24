#!/usr/bin/env python3
"""
VM-Harness CI/CD — Android Track
─────────────────────────────────
Prepare → Preflight → Test → Build → Deploy
for the Kotlin/Jetpack Compose Android application.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ci.common import (
    Ansi,
    Logger,
    PhaseResult,
    ProcessResult,
    TrackResult,
    ensure_dir,
    file_exists,
    file_size,
    file_size_human,
    git_head_commit,
    git_status,
    git_version_tag,
    now_iso,
    run_command,
    sha256_file,
    write_json_report,
    write_text_report,
    write_yaml_report,
    duration_human,
)

# ── Android SDK / JDK discovery ───────────────────────────────────────────────

def _find_java(logger: Logger) -> str | None:
    """Find a usable Java executable."""
    candidates = [
        r"C:\Program Files\Android\Android Studio\jbr\bin\java.exe",
        r"C:\Program Files\Java\jdk-17\bin\java.exe",
        r"C:\Program Files\Java\jdk-18\bin\java.exe",
        r"C:\Program Files\Java\jdk-21\bin\java.exe",
        "java",
    ]
    for c in candidates:
        path = c if isinstance(c, Path) else Path(c)
        if path.exists() or c == "java":
            r = run_command([c, "-version"], capture=True, logger=None)
            if r.succeeded and "openjdk" in (r.stdout + r.stderr).lower():
                logger.success(f"Java: {c if isinstance(c, str) else str(c)} — {(r.stdout + r.stderr).strip().splitlines()[0]}")
                return c
    logger.error("No usable Java found")
    return None


def _find_android_sdk_root(logger: Logger) -> str | None:
    """Find the Android SDK root directory."""
    candidates = [
        os.environ.get("ANDROID_SDK_ROOT", ""),
        os.environ.get("ANDROID_HOME", ""),
        r"C:\Users\Server\soniccore-toolchain\sdk",
        r"C:\Android\sdk",
        r"C:\Users\Public\Android\sdk",
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists() and (p / "platforms").exists():
            # Verify it has a usable platform
            platforms = list(p.glob("platforms/android-*"))
            if platforms:
                logger.success(f"Android SDK: {c} (platforms: {', '.join(str(pp.name) for pp in platforms)})")
                return c
            logger.warn(f"Android SDK path exists but no platforms: {c}")
    logger.error("No Android SDK found")
    return None


def _find_gradle_wrapper(android_dir: Path, logger: Logger) -> Path | None:
    """Find the Gradle wrapper script."""
    candidates = [
        android_dir / "gradlew.bat",
        android_dir / "gradlew",
        android_dir / "gradle" / "gradlew.bat",
        android_dir / "gradle" / "gradlew",
    ]
    for c in candidates:
        if c.exists():
            logger.success(f"Gradle wrapper: {c.name} ({file_size_human(c)})")
            return c
    logger.error(f"No Gradle wrapper found in {android_dir}")
    return None


def _get_gradle_version(android_dir: Path, logger: Logger) -> str | None:
    """Get the Gradle version from the wrapper properties."""
    props = android_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not props.exists():
        return None
    content = props.read_text(encoding="utf-8")
    # Extract Gradle version from distributionUrl (handles both forward and back slashes)
    match = re.search(r"gradle[_-]?(\d+\.\d+(?:\.\d+)?)", content)
    if match:
        return match.group(1)
    return None


# ── Android preflight checks ──────────────────────────────────────────────────


def _check_manifest(android_dir: Path, logger: Logger) -> dict[str, Any]:
    """Validate AndroidManifest.xml for required elements."""
    manifest = android_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    results = {"file": str(manifest), "exists": manifest.exists()}
    if not manifest.exists():
        return results

    content = manifest.read_text(encoding="utf-8")
    checks = {}

    # Package name (legacy attribute or namespace from build.gradle.kts)
    pkg_match = re.search(r'package\s*=\s*["\']([^"\']+)["\']', content)
    if pkg_match:
        checks["package"] = pkg_match.group(1)
    else:
        # Fall back to namespace from build.gradle.kts
        build_gradle = android_dir / "app" / "build.gradle.kts"
        if build_gradle.exists():
            bg = build_gradle.read_text(encoding="utf-8")
            ns_match = re.search(r'namespace\s*=\s*["\']([^"\']+)["\']', bg)
            checks["package"] = ns_match.group(1) if ns_match else "NOT FOUND"
        else:
            checks["package"] = "NOT FOUND"

    # Application ID (should match or be overrideable)
    app_id_match = re.search(r'android:label="([^"]*)"', content)
    checks["label"] = app_id_match.group(1) if app_id_match else "NOT FOUND"

    # Target SDK
    target_match = re.search(r'targetSdkVersion[^0-9]*(\d+)', content)
    checks["targetSdk"] = target_match.group(1) if target_match else "NOT FOUND"

    # Min SDK
    min_match = re.search(r'minSdkVersion[^0-9]*(\d+)', content)
    checks["minSdk"] = min_match.group(1) if min_match else "NOT FOUND"

    # Deep link scheme
    scheme_match = re.search(r'android:scheme="([^"]+)"', content)
    checks["deep_link_scheme"] = scheme_match.group(1) if scheme_match else "NOT FOUND"

    # Permissions
    perms = re.findall(r'<uses-permission[^>]*android:name="([^"]+)"', content)
    checks["permissions"] = perms

    # Activities
    activities = re.findall(r'<activity[^>]*android:name="([^"]+)"', content)
    checks["activities"] = activities

    # Deep link intent filter
    dl_filter = "<data" in content and 'scheme="vmharness"' in content
    checks["deep_link_configured"] = dl_filter

    results["checks"] = checks
    return results


def _check_build_gradle(android_dir: Path, logger: Logger) -> dict[str, Any]:
    """Validate app/build.gradle.kts for consistency."""
    build_file = android_dir / "app" / "build.gradle.kts"
    results = {"file": str(build_file), "exists": build_file.exists()}
    if not build_file.exists():
        return results

    content = build_file.read_text(encoding="utf-8")

    # Extract key values
    namespace_match = re.search(r'namespace\s*=\s*"([^"]+)"', content)
    results["namespace"] = namespace_match.group(1) if namespace_match else "NOT FOUND"

    compile_sdk_match = re.search(r'compileSdk\s*=\s*(\d+)', content)
    results["compileSdk"] = compile_sdk_match.group(1) if compile_sdk_match else "NOT FOUND"

    min_sdk_match = re.search(r'minSdk\s*=\s*(\d+)', content)
    results["minSdk"] = min_sdk_match.group(1) if min_sdk_match else "NOT FOUND"

    target_sdk_match = re.search(r'targetSdk\s*=\s*(\d+)', content)
    results["targetSdk"] = target_sdk_match.group(1) if target_sdk_match else "NOT FOUND"

    version_code_match = re.search(r'versionCode\s*=\s*(\d+)', content)
    results["versionCode"] = version_code_match.group(1) if version_code_match else "NOT FOUND"

    version_name_match = re.search(r'versionName\s*=\s*"([^"]+)"', content)
    results["versionName"] = version_name_match.group(1) if version_name_match else "NOT FOUND"

    # Check dependencies
    deps_section = re.search(r'dependencies\s*\{(.*?)\}', content, re.DOTALL)
    if deps_section:
        deps_text = deps_section.group(1)
        deps = re.findall(r'implementation\s*\(?\s*["\']([^"\']+)["\']', deps_text)
        results["dependencies"] = deps

    # Check plugins
    plugins_match = re.search(r'plugins\s*\{(.*?)\}', content, re.DOTALL)
    if plugins_match:
        plugins_text = plugins_match.group(1)
        plugins_list = re.findall(r'id\s*\(\s*["\']([^"\']+)["\']', plugins_text)
        results["plugins"] = plugins_list

    return results


def _check_kotlin_compile(android_dir: Path, gradle_wrapper: Path, logger: Logger) -> ProcessResult:
    """Run ./gradlew compileDebugKotlin to verify compilation."""
    cmd = [str(gradle_wrapper), "compileDebugKotlin", "--no-daemon"]
    return run_command(cmd, cwd=android_dir, timeout_s=300, logger=logger)


def _check_gradle_dependencies(android_dir: Path, gradle_wrapper: Path, logger: Logger) -> ProcessResult:
    """Run ./gradlew dependencies to verify all dependencies resolve."""
    cmd = [str(gradle_wrapper), "app:dependencies", "--no-daemon", "--configuration", "debugCompileClasspath"]
    return run_command(cmd, cwd=android_dir, timeout_s=300, logger=logger)


def _check_android_lint(android_dir: Path, gradle_wrapper: Path, logger: Logger) -> ProcessResult:
    """Run ./gradlew lintDebug for lint checks."""
    cmd = [str(gradle_wrapper), "lintDebug", "--no-daemon"]
    return run_command(cmd, cwd=android_dir, timeout_s=300, logger=logger)


def _check_unit_tests(android_dir: Path, gradle_wrapper: Path, logger: Logger) -> ProcessResult:
    """Run ./gradlew testDebugUnitTest for unit tests."""
    cmd = [str(gradle_wrapper), "testDebugUnitTest", "--no-daemon"]
    return run_command(cmd, cwd=android_dir, timeout_s=300, logger=logger)


def _check_instrumented_tests(android_dir: Path, gradle_wrapper: Path, logger: Logger) -> ProcessResult:
    """Run ./gradlew connectedAndroidTest (requires device/emulator)."""
    cmd = [str(gradle_wrapper), "connectedAndroidTest", "--no-daemon"]
    return run_command(cmd, cwd=android_dir, timeout_s=600, logger=logger)


# ── Android build ─────────────────────────────────────────────────────────────


def _build_debug_apk(
    android_dir: Path,
    gradle_wrapper: Path,
    logger: Logger,
) -> ProcessResult:
    """Build the debug APK."""
    cmd = [str(gradle_wrapper), "assembleDebug", "--no-daemon"]
    return run_command(cmd, cwd=android_dir, timeout_s=600, logger=logger)


def _build_release_apk(
    android_dir: Path,
    gradle_wrapper: Path,
    logger: Logger,
    keystore: str | None = None,
    alias: str | None = None,
    password_env: str | None = None,
) -> ProcessResult:
    """Build the release APK (requires signing config)."""
    if not keystore or not alias:
        logger.warn("Release build requested but no keystore/alias configured — skipping")
        return ProcessResult(-1, "", "No keystore configured", 0, False, "assembleRelease", str(android_dir))

    password = os.environ.get(password_env, "") if password_env else ""
    cmd = [str(gradle_wrapper), "assembleRelease", "--no-daemon"]
    # Pass signing info via environment
    env = {}
    if password:
        env["ANDROID_RELEASE_KEYSTORE_PASSWORD"] = password
    return run_command(cmd, cwd=android_dir, timeout_s=600, logger=logger, env=env)


def _find_apk(android_dir: Path, build_type: str = "debug") -> Path | None:
    """Find the built APK."""
    apk_name = f"app-{build_type}.apk"
    apk_path = android_dir / "app" / "build" / "outputs" / "apk" / build_type / apk_name
    if apk_path.exists():
        return apk_path
    # Fallback: search
    for p in (android_dir / "app" / "build" / "outputs" / "apk" / build_type).rglob("*.apk"):
        return p
    return None


def _extract_apk_metadata(apk_path: Path, logger: Logger) -> dict[str, Any]:
    """Extract APK metadata using aapt or basic analysis."""
    results = {"file": str(apk_path), "size_bytes": file_size(apk_path)}

    # Try aapt
    aapt_candidates = [
        Path(r"C:\Users\Server\soniccore-toolchain\sdk\build-tools\35.0.0\aapt.exe"),
        Path(r"C:\Users\Server\soniccore-toolchain\sdk\build-tools\34.0.0\aapt.exe"),
    ]
    aapt = None
    for c in aapt_candidates:
        if c.exists():
            aapt = c
            break

    if aapt:
        try:
            r = run_command([str(aapt), "dump", "badging", str(apk_path)], capture=True, logger=logger)
            if r.succeeded:
                for line in r.stdout.split("\n"):
                    if line.startswith("package:"):
                        pkg_match = re.search(r'name=(\S+)', line)
                        ver_match = re.search(r'versionCode=(\d+)', line)
                        vername_match = re.search(r'versionName=(\S+)', line)
                        if pkg_match:
                            results["package"] = pkg_match.group(1)
                        if ver_match:
                            results["versionCode"] = ver_match.group(1)
                        if vername_match:
                            results["versionName"] = vername_match.group(1).strip("'")
                    if line.startswith("sdkVersion:"):
                        results["minSdk"] = line.split(":")[1].strip()
        except Exception as e:
            logger.warn(f"aapt failed: {e}")

    # Fallback: parse AndroidManifest.xml from APK (it's a zip)
    try:
        with zipfile.ZipFile(apk_path, "r") as zf:
            if "AndroidManifest.xml" in zf.namelist():
                # AndroidManifest.xml is binary — use basic extraction
                results["has_manifest"] = True
                results["is_apk"] = True
    except Exception:
        results["is_apk"] = False

    return results


# ── Android deploy ────────────────────────────────────────────────────────────


def _package_apk_artifacts(
    apk_path: Path,
    artifact_dir: Path,
    checksum: bool = True,
    report: bool = True,
    logger: Logger | None = None,
) -> dict[str, Any]:
    """Copy APK to artifact dir, generate checksum + report."""
    ensure_dir(artifact_dir)

    apk_name = apk_path.name
    dest = artifact_dir / apk_name
    shutil.copy2(apk_path, dest)

    results = {"apk_copied": str(dest), "apk_size": file_size(apk_path)}

    if checksum:
        sha = sha256_file(apk_path)
        sha_file = artifact_dir / f"{apk_name}.sha256"
        sha_file.write_text(f"{sha}  {apk_name}\n")
        results["sha256"] = sha
        results["checksum_file"] = str(sha_file)
        if logger:
            logger.success(f"  SHA256: {sha[:16]}...")

    if report:
        report_file = artifact_dir / f"{apk_name}.report.txt"
        lines = [
            f"APK Report: {apk_name}",
            f"Generated: {now_iso()}",
            f"",
            f"File: {apk_name}",
            f"Size: {file_size_human(apk_path)} ({file_size(apk_path)} bytes)",
            f"SHA256: {sha if checksum else 'N/A'}",
            "",
        ]
        write_text_report(report_file, lines)
        results["report_file"] = str(report_file)
        if logger:
            logger.success(f"  Report: {report_file}")

    return results


# ── Android Track Pipeline ────────────────────────────────────────────────────


def run_android_pipeline(
    root: str | Path = ".",
    config: dict[str, Any] | None = None,
    logger: Logger | None = None,
    phases_to_run: list[str] | None = None,
) -> TrackResult:
    """Run the full Android CI/CD pipeline.

    Args:
        root: Project root directory (default: current directory).
        config: Pipeline config dict (loaded from ci/config.yaml by default).
        logger: Logger instance (creates default if None).
        phases_to_run: Specific phases to run. None = all enabled phases.
    """
    root = Path(root).resolve()
    android_dir = root / "android"
    if logger is None:
        logger = Logger(LogLevel.INFO)

    cfg = config or {}
    android_cfg = cfg.get("android", {})
    if not android_cfg.get("enabled", True):
        logger.info("Android track disabled in config — skipping")
        return TrackResult(
            track="android",
            overall_status="skipped",
            start_time=now_iso(),
            end_time=now_iso(),
        )

    logger.section(f"ANDROID PIPELINE — VM-Harness Android ({android_dir})")

    track_result = TrackResult(
        track="android",
        start_time=now_iso(),
    )

    if phases_to_run is None:
        phases_to_run = ["prepare", "preflight", "test", "build", "deploy"]

    fail_fast = cfg.get("global", {}).get("fail_fast", True)

    # Discover toolchain (needed by multiple phases)
    java = _find_java(logger)
    sdk_root = _find_android_sdk_root(logger)
    gradle_wrapper = _find_gradle_wrapper(android_dir, logger)
    gradle_version = _get_gradle_version(android_dir, logger) if gradle_wrapper else None

    # Store toolchain info for phases
    toolchain = {
        "java": java,
        "sdk_root": sdk_root,
        "gradle_wrapper": str(gradle_wrapper) if gradle_wrapper else None,
        "gradle_version": gradle_version,
    }

    for phase_name in phases_to_run:
        if phase_name == "prepare":
            result = phase_android_prepare(android_dir, android_cfg, toolchain, logger)
        elif phase_name == "preflight":
            result = phase_android_preflight(android_dir, android_cfg, toolchain, logger)
        elif phase_name == "test":
            result = phase_android_test(android_dir, android_cfg, toolchain, logger)
        elif phase_name == "build":
            result = phase_android_build(android_dir, android_cfg, toolchain, logger)
        elif phase_name == "deploy":
            result = phase_android_deploy(android_dir, android_cfg, toolchain, logger)
        else:
            result = PhaseResult(
                track="android",
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

    statuses = [p.status for p in track_result.phases]
    if "failed" in statuses:
        track_result.overall_status = "failed"
    elif all(s == "skipped" for s in statuses):
        track_result.overall_status = "skipped"
    else:
        track_result.overall_status = "passed"

    track_result.end_time = now_iso()
    logger.section(f"ANDROID PIPELINE COMPLETE — Status: {track_result.overall_status.upper()}")

    return track_result


# ── Phase: Prepare ────────────────────────────────────────────────────────────


def phase_android_prepare(
    android_dir: Path,
    cfg: dict[str, Any],
    toolchain: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Prepare phase: check JDK, Android SDK, Gradle wrapper, dependency resolution."""
    phase_start = time.monotonic()
    logger.subsection("ANDROID PREPARE PHASE")

    checks: list[tuple[str, bool, str]] = []

    # Java check
    if cfg.get("check_java", True):
        java = toolchain.get("java")
        if java:
            r = run_command([java, "-version"], capture=True, logger=logger)
            version_line = (r.stdout + r.stderr).strip().split("\n")[0]
            # Parse version
            ver_match = re.search(r"(\d+)\.(\d+)", version_line)
            ok = False
            msg = ""
            if ver_match:
                major = int(ver_match.group(1))
                min_ver = cfg.get("java_version_min", "17")
                min_major = int(min_ver.split(".")[0])
                ok = major >= min_major
                msg = f"Java {version_line} (>= {min_ver}: {'OK' if ok else 'LOWER'})"
            else:
                msg = f"Java found: {version_line}"
                ok = True
            checks.append(("java", ok, msg))
            if not ok:
                logger.error(msg)

    # Android SDK check
    if cfg.get("check_android_sdk", True):
        sdk = toolchain.get("sdk_root")
        if sdk:
            sdk_path = Path(sdk)
            platforms = list(sdk_path.glob("platforms/android-*"))
            build_tools = list(sdk_path.glob("build-tools/*"))
            ok = len(platforms) > 0 and len(build_tools) > 0
            msg = f"SDK: {sdk} — {len(platforms)} platforms, {len(build_tools)} build-tools"
            checks.append(("android_sdk", ok, msg))
            if not ok:
                logger.error(msg)
        else:
            checks.append(("android_sdk", False, "Android SDK not found"))
            logger.error("Android SDK not found")

    # Gradle wrapper check
    if cfg.get("check_gradle_wrapper", True):
        gw = toolchain.get("gradle_wrapper")
        if gw:
            exists = Path(gw).exists()
            gv = toolchain.get("gradle_version", "unknown")
            checks.append(("gradle_wrapper", exists, f"Gradle {gv} wrapper found" if exists else "wrapper missing"))
            if not exists:
                logger.error("Gradle wrapper not found")
        else:
            checks.append(("gradle_wrapper", False, "Gradle wrapper not found"))
            logger.error("Gradle wrapper not found")

    # Dependency resolution (optional — can be slow)
    if cfg.get("check_dependencies_resolve", True):
        gw = toolchain.get("gradle_wrapper")
        if gw:
            logger.info("  Verifying Gradle dependencies resolve...")
            r = run_command(
                [gw, "app:dependencies", "--no-daemon", "--configuration", "debugCompileClasspath"],
                cwd=android_dir,
                timeout_s=300,
                logger=logger,
            )
            deps_ok = r.succeeded
            checks.append(("dependency_resolution", deps_ok, f"resolved" if deps_ok else f"failed (exit {r.returncode})"))
            if not deps_ok:
                logger.error(f"  Dependency resolution failed: {r.stderr[-300:]}")

    # Compile SDK check
    if cfg.get("check_compile_sdk"):
        compile_sdk = cfg.get("check_compile_sdk")
        sdk = toolchain.get("sdk_root")
        if sdk and compile_sdk:
            platform_dir = Path(sdk) / "platforms" / f"android-{compile_sdk}"
            ok = platform_dir.exists()
            checks.append(("compile_sdk", ok, f"android-{compile_sdk} platform {'present' if ok else 'MISSING'}"))
            if not ok:
                logger.error(f"  Target platform android-{compile_sdk} not installed")

    # Min SDK check
    if cfg.get("check_min_sdk"):
        min_sdk = cfg.get("check_min_sdk")
        # Just verify it's a reasonable number
        ok = isinstance(min_sdk, int) and min_sdk >= 21
        checks.append(("min_sdk", ok, f"minSdk={min_sdk} ({'OK' if ok else 'too low'})"))

    passed_count = sum(1 for _, ok, _ in checks if ok)
    total_count = len(checks)
    all_ok = passed_count == total_count

    return PhaseResult(
        track="android",
        phase="prepare",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} prepare checks passed",
        details={
            "java": toolchain.get("java"),
            "sdk_root": toolchain.get("sdk_root"),
            "gradle_wrapper": toolchain.get("gradle_wrapper"),
            "gradle_version": toolchain.get("gradle_version"),
            "checks": {name: {"passed": ok, "message": msg} for name, ok, msg in checks},
        },
    )


# ── Phase: Preflight ──────────────────────────────────────────────────────────


def phase_android_preflight(
    android_dir: Path,
    cfg: dict[str, Any],
    toolchain: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Preflight phase: manifest check, build.gradle check, compile check, lint."""
    phase_start = time.monotonic()
    logger.subsection("ANDROID PREFLIGHT PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    gw = toolchain.get("gradle_wrapper")
    gw_path = Path(gw) if gw else None

    # Manifest validation
    if cfg.get("manifest_validation", True):
        manifest_results = _check_manifest(android_dir, logger)
        manifest_ok = (
            manifest_results.get("exists", False)
            and manifest_results.get("checks", {}).get("package") != "NOT FOUND"
            and manifest_results.get("checks", {}).get("deep_link_configured", False)
        )
        checks.append(("manifest_validation", manifest_ok, f"package={manifest_results.get('checks', {}).get('package', 'N/A')}", manifest_results))
        if not manifest_ok:
            logger.error(f"  Manifest issues: package={'OK' if manifest_results.get('checks', {}).get('package') != 'NOT FOUND' else 'MISSING'}, deep_link={'OK' if manifest_results.get('checks', {}).get('deep_link_configured') else 'MISSING'})")

    # Build.gradle check
    if cfg.get("check_build_gradle_consistency", True):
        build_results = _check_build_gradle(android_dir, logger)
        build_ok = (
            build_results.get("exists", False)
            and build_results.get("namespace") != "NOT FOUND"
            and build_results.get("compileSdk") != "NOT FOUND"
        )
        checks.append(("build_gradle_check", build_ok, f"namespace={build_results.get('namespace', 'N/A')} compileSdk={build_results.get('compileSdk', 'N/A')}", build_results))
        if not build_ok:
            logger.error(f"  Build.gradle issues: namespace={'OK' if build_results.get('namespace') != 'NOT FOUND' else 'MISSING'}, compileSdk={'OK' if build_results.get('compileSdk') != 'NOT FOUND' else 'MISSING'}")

    # Deep link scheme check
    if cfg.get("check_deep_link_scheme", True):
        manifest_results = _check_manifest(android_dir, logger)
        dl_ok = manifest_results.get("checks", {}).get("deep_link_scheme") == "vmharness"
        checks.append(("deep_link_scheme", dl_ok, f"scheme={manifest_results.get('checks', {}).get('deep_link_scheme', 'N/A')}", {}))

    # Kotlin compile check
    if cfg.get("kotlin_compile_check", True) and gw_path:
        logger.info("  Running Kotlin compile check (compileDebugKotlin)...")
        r = _check_kotlin_compile(android_dir, gw_path, logger)
        compile_ok = r.succeeded
        checks.append(("kotlin_compile", compile_ok, f"compile {'OK' if compile_ok else 'FAILED'} (exit {r.returncode})", {
            "exit_code": r.returncode,
            "duration_s": r.duration_s,
        }))
        if not compile_ok:
            logger.error(f"  Kotlin compile failed: {r.stderr[-500:]}")

    # Lint check
    if cfg.get("run_lint", True) and gw_path:
        logger.info("  Running Android Lint (lintDebug)...")
        r = _check_android_lint(android_dir, gw_path, logger)
        lint_ok = r.succeeded
        checks.append(("android_lint", lint_ok, f"lint {'OK' if lint_ok else 'FAILED'} (exit {r.returncode})", {
            "exit_code": r.returncode,
            "duration_s": r.duration_s,
        }))
        if not lint_ok:
            logger.error(f"  Lint failed: {r.stderr[-500:]}")

    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)
    all_ok = passed_count == total_count

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="android",
        phase="preflight",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} preflight checks passed",
        details=details,
    )


# ── Phase: Test ───────────────────────────────────────────────────────────────


def phase_android_test(
    android_dir: Path,
    cfg: dict[str, Any],
    toolchain: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Test phase: unit tests, lint tests."""
    phase_start = time.monotonic()
    logger.subsection("ANDROID TEST PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    gw = toolchain.get("gradle_wrapper")
    gw_path = Path(gw) if gw else None

    # Unit tests
    if cfg.get("run_unit_tests", True) and gw_path:
        logger.info("  Running unit tests (testDebugUnitTest)...")
        r = _check_unit_tests(android_dir, gw_path, logger)
        tests_ok = r.succeeded
        # Parse output for test counts
        import re
        passed_match = re.search(r"(\d+)\s+tests?,\s+(\d+)\s+failed", r.stdout)
        if passed_match:
            n_passed = int(passed_match.group(1))
            n_failed = int(passed_match.group(2))
            msg = f"{n_passed} tests, {n_failed} failed"
            test_ok = n_failed == 0
        else:
            n_passed = 0
            n_failed = 0 if r.succeeded else 1
            msg = f"tests {'passed' if r.succeeded else 'failed'} (exit {r.returncode})"
            test_ok = r.succeeded
        checks.append(("unit_tests", test_ok, msg, {
            "exit_code": r.returncode,
            "duration_s": r.duration_s,
            "passed": n_passed,
            "failed": n_failed,
        }))
        if not test_ok:
            logger.error(f"  Unit tests: {msg}")

    # Lint test
    if cfg.get("run_lint", True) and gw_path:
        logger.info("  Running lint (as test phase verification)...")
        r = _check_android_lint(android_dir, gw_path, logger)
        lint_ok = r.succeeded
        checks.append(("lint_tests", lint_ok, f"lint {'passed' if lint_ok else 'failed'} (exit {r.returncode})", {
            "exit_code": r.returncode,
            "duration_s": r.duration_s,
        }))

    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)
    all_ok = passed_count == total_count

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="android",
        phase="test",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} test checks passed",
        details=details,
    )


# ── Phase: Build ──────────────────────────────────────────────────────────────


def phase_android_build(
    android_dir: Path,
    cfg: dict[str, Any],
    toolchain: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Build phase: assemble debug APK (and optionally release)."""
    phase_start = time.monotonic()
    logger.subsection("ANDROID BUILD PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    gw = toolchain.get("gradle_wrapper")
    gw_path = Path(gw) if gw else None

    # Debug APK build
    if cfg.get("build_debug_apk", True) and gw_path:
        logger.info("  Building debug APK (assembleDebug)...")
        r = _build_debug_apk(android_dir, gw_path, logger)
        build_ok = r.succeeded
        apk_path = _find_apk(android_dir, "debug")
        apk_exists = apk_path is not None

        # Extract APK metadata
        apk_meta = {}
        if apk_exists:
            apk_meta = _extract_apk_metadata(apk_path, logger)

        checks.append(("debug_apk_build", build_ok and apk_exists, f"APK {'built' if apk_exists else 'not found'} ({file_size_human(apk_path) if apk_exists else 'N/A'})", {
            "exit_code": r.returncode,
            "duration_s": r.duration_s,
            "apk_path": str(apk_path) if apk_path else None,
            "apk_size_bytes": file_size(apk_path) if apk_path else 0,
            "apk_metadata": apk_meta,
        }))
        if not build_ok:
            logger.error(f"  Debug APK build failed: {r.stderr[-500:]}")
        if not apk_exists:
            logger.error(f"  Debug APK not found after build")
        else:
            logger.success(f"  Debug APK: {apk_path} ({file_size_human(apk_path)})")

    # Release APK build
    if cfg.get("build_release_apk", True) and gw_path:
        release_cfg = cfg.get("deploy", {})
        keystore = release_cfg.get("release_keystore", "")
        alias = release_cfg.get("release_alias", "")
        password_env = release_cfg.get("release_password_env", "ANDROID_RELEASE_KEYSTORE_PASSWORD")
        if keystore and alias:
            logger.info("  Building release APK (assembleRelease)...")
            r = _build_release_apk(android_dir, gw_path, logger, keystore, alias, password_env)
            rel_build_ok = r.succeeded
            rel_apk = _find_apk(android_dir, "release")
            rel_exists = rel_apk is not None
            checks.append(("release_apk_build", rel_build_ok and rel_exists, f"Release APK {'built' if rel_exists else 'not found'}", {
                "exit_code": r.returncode,
                "duration_s": r.duration_s,
                "apk_path": str(rel_apk) if rel_apk else None,
            }))
            if rel_build_ok and rel_exists:
                logger.success(f"  Release APK: {rel_apk} ({file_size_human(rel_apk)})")
            else:
                logger.error(f"  Release APK build: {'failed' if not rel_build_ok else 'APK not found'}")
        else:
            checks.append(("release_apk_build", False, "Skipped — no keystore configured", {"reason": "no_keystore"}))

    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)
    all_ok = passed_count == total_count

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="android",
        phase="build",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} build checks passed",
        details=details,
    )


# ── Phase: Deploy ─────────────────────────────────────────────────────────────


def phase_android_deploy(
    android_dir: Path,
    cfg: dict[str, Any],
    toolchain: dict[str, Any],
    logger: Logger,
) -> PhaseResult:
    """Deploy phase: package APK artifacts, generate checksums + reports."""
    phase_start = time.monotonic()
    logger.subsection("ANDROID DEPLOY PHASE")

    checks: list[tuple[str, bool, str, dict[str, Any]]] = []

    deploy_cfg = cfg.get("deploy", {})
    artifact_dir = Path(deploy_cfg.get("output_dir", str(android_dir / "build" / "outputs" / "artifacts")))
    version_name = None

    # Copy debug APK
    if deploy_cfg.get("copy_debug_apk", True):
        apk_path = _find_apk(android_dir, "debug")
        if apk_path and apk_path.exists():
            logger.info(f"  Packaging debug APK: {apk_path.name}")
            pkg_results = _package_apk_artifacts(
                apk_path,
                artifact_dir,
                checksum=deploy_cfg.get("generate_checksums", True),
                report=deploy_cfg.get("generate_apk_report", True),
                logger=logger,
            )
            version_name = pkg_results.get("apk_metadata", {}).get("versionName")
            checks.append(("package_debug_apk", True, f"Packaged: {apk_path.name} → {artifact_dir}", pkg_results))
        else:
            logger.error("  Debug APK not found — cannot package")
            checks.append(("package_debug_apk", False, "Debug APK not found"))

    # Copy release APK
    if deploy_cfg.get("copy_release_apk", False):
        apk_path = _find_apk(android_dir, "release")
        if apk_path and apk_path.exists():
            logger.info(f"  Packaging release APK: {apk_path.name}")
            pkg_results = _package_apk_artifacts(apk_path, artifact_dir, checksum=True, report=True, logger=logger)
            checks.append(("package_release_apk", True, f"Packaged: {apk_path.name}", pkg_results))
        else:
            logger.warn("  Release APK not found — skipping")
            checks.append(("package_release_apk", False, "Release APK not found"))

    # Version info
    git_tag = git_version_tag(android_dir.parent)
    git_head = git_head_commit(android_dir.parent)
    logger.info(f"  Git tag: {git_tag or 'none'}")
    logger.info(f"  Git head: {git_head}")

    # Generate APK build report (markdown)
    if deploy_cfg.get("generate_apk_report", True):
        report_file = artifact_dir / "APK_BUILD_REPORT.md"
        lines = [
            f"# VM-Harness Android APK Build Report",
            "",
            f"- **Version:** {version_name or 'unknown'}",
            f"- **Git tag:** {git_tag or 'not tagged'}",
            f"- **Git commit:** {git_head}",
            f"- **Generated:** {now_iso()}",
            "",
            "## Artifacts",
            "",
        ]
        for apk_file in sorted(artifact_dir.glob("*.apk")):
            sha = sha256_file(apk_file)
            lines.append(f"- `{apk_file.name}` — {file_size_human(apk_file)} — SHA256: `{sha[:16]}...`")
        lines.extend([
            "",
            "## Build Configuration",
            "",
            f"- **minSdk:** {cfg.get('prepare', {}).get('check_min_sdk', 'unknown')}",
            f"- **compileSdk:** {cfg.get('prepare', {}).get('check_compile_sdk', 'unknown')}",
            f"- **targetSdk:** {cfg.get('build', {}).get('expected_target_sdk', 'unknown')}",
            "",
            "---",
            f"*Generated by VM-Harness CI/CD pipeline — {now_iso()}*",
        ])
        report_file.write_text("\n".join(lines) + "\n")
        logger.success(f"  Build report: {report_file}")
        checks.append(("build_report", True, f"Written: {report_file.name}", {"file": str(report_file)}))

    passed_count = sum(1 for _, ok, _, _ in checks if ok)
    total_count = len(checks)
    all_ok = passed_count == total_count

    details = {}
    for name, ok, msg, detail in checks:
        details[name] = {"passed": ok, "message": msg, **(detail if isinstance(detail, dict) else {})}

    return PhaseResult(
        track="android",
        phase="deploy",
        status="passed" if all_ok else "failed",
        duration_s=time.monotonic() - phase_start,
        message=f"{passed_count}/{total_count} deploy checks passed",
        details=details,
    )


# ── Report formatting helpers ─────────────────────────────────────────────────


def format_track_report(result: TrackResult, config: dict[str, Any] | None = None) -> list[str]:
    """Format a TrackResult as a human-readable text report."""
    lines = []
    lines.append(f"VM-Harness CI/CD — Android Track Report")
    lines.append(f"Generated: {now_iso()}")
    lines.append(f"Status: {result.overall_status.upper()}")
    lines.append("")
    for phase in result.phases:
        lines.append(f"## {phase.phase.upper()}")
        lines.append(f"Status: {phase.status.upper()}")
        lines.append(f"Duration: {duration_human(phase.duration_s)}")
        if phase.message:
            lines.append(f"Message: {phase.message}")
        if phase.details:
            lines.append("Details:")
            for key, val in phase.details.items():
                if isinstance(val, dict):
                    lines.append(f"  {key}:")
                    for k, v in val.items():
                        if isinstance(v, (dict, list)):
                            lines.append(f"    {k}: {json.dumps(v)[:200]}")
                        else:
                            lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  {key}: {val}")
        lines.append("")
    return lines


def serialize_track_result(result: TrackResult) -> dict[str, Any]:
    """Convert a TrackResult to a JSON-serializable dict."""
    return {
        "track": result.track,
        "overall_status": result.overall_status,
        "start_time": result.start_time,
        "end_time": result.end_time,
        "phases": [
            {
                "phase": p.phase,
                "status": p.status,
                "duration_s": p.duration_s,
                "message": p.message,
                "details": p.details,
                "error": p.error,
            }
            for p in result.phases
        ],
    }
