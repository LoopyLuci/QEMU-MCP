#!/usr/bin/env python3
"""
VM-Harness On-Device CI/CD Pipeline — Master Orchestrator
─────────────────────────────────────────────────────────
Runs desktop (Python/PyQt5) and Android (Kotlin/Compose) tracks
with configurable phases, gating, parallelism, and reporting.

Usage:
  python ci/pipeline.py                  # run all phases, both tracks
  python ci/pipeline.py --track desktop  # desktop only
  python ci/pipeline.py --track android  # android only
  python ci/pipeline.py --phase test     # run test phase only (both tracks)
  python ci/pipeline.py --phase build --track desktop  # build desktop only
  python ci/pipeline.py --parallel      # run tracks in parallel
  python ci/pipeline.py --dry-run       # show what would run, don't execute
  python ci/pipeline.py --report-only   # regenerate reports from last run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure the project root is on the path so 'ci' is importable as a package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ci.common import (
    Logger,
    LogLevel,
    PhaseResult,
    PipelineResult,
    TrackResult,
    deserialize_pipeline_result,
    ensure_dir,
    now_iso,
    run_command,
    sha256_file,
    write_json_report,
    write_text_report,
    write_yaml_report,
    load_config,
    git_status,
    git_head_commit,
    git_version_tag,
    get_desktop_version,
)

# Try to import track modules
try:
    from ci.desktop import run_desktop_pipeline
    DESKTOP_AVAILABLE = True
except ImportError as e:
    DESKTOP_AVAILABLE = False
    _DESKTOP_IMPORT_ERROR = str(e)

try:
    from ci.android import run_android_pipeline
    ANDROID_AVAILABLE = True
except ImportError as e:
    ANDROID_AVAILABLE = False
    _ANDROID_IMPORT_ERROR = str(e)


# ── Pipeline Orchestrator ─────────────────────────────────────────────────────

class PipelineOrchestrator:
    """Manages execution of desktop and/or Android CI/CD tracks."""

    def __init__(
        self,
        root: Path,
        config: dict[str, Any],
        logger: Logger,
        tracks_to_run: list[str] | None = None,
        phases_to_run: list[str] | None = None,
        parallel: bool = False,
        dry_run: bool = False,
    ):
        self.root = root
        self.config = config
        self.logger = logger
        self.tracks_to_run = tracks_to_run or self._detect_tracks()
        self.phases_to_run = phases_to_run or self._detect_phases()
        self.parallel = parallel
        self.dry_run = dry_run
        self.report_dir = ensure_dir(root / "ci" / "report")
        self.artifact_dir = ensure_dir(root / "ci" / "artifacts")
        self.result = PipelineResult(
            start_time=now_iso(),
            config=config,
        )

    def _detect_tracks(self) -> list[str]:
        """Detect which tracks to run based on config and availability."""
        cfg = self.config
        tracks = []
        if cfg.get("desktop", {}).get("enabled", True):
            if DESKTOP_AVAILABLE:
                tracks.append("desktop")
            else:
                self.logger.error(f"Desktop track enabled but module unavailable: {_DESKTOP_IMPORT_ERROR}")
        if cfg.get("android", {}).get("enabled", True):
            if ANDROID_AVAILABLE:
                tracks.append("android")
            else:
                self.logger.error(f"Android track enabled but module unavailable: {_ANDROID_IMPORT_ERROR}")
        # If no tracks detected but user didn't specify, show error
        if not tracks and not self.tracks_to_run:
            self.logger.error("No tracks available to run — check imports and config")
        return tracks

    def _detect_phases(self) -> list[str]:
        """Default: run all phases."""
        all_phases = ["prepare", "preflight", "test", "build", "deploy"]
        return all_phases

    def run(self) -> PipelineResult:
        """Execute the pipeline."""
        self.logger.section("VM-Harness ON-DEVICE CI/CD PIPELINE")
        self.logger.info(f"Project root: {self.root}")
        self.logger.info(f"Tracks: {', '.join(self.tracks_to_run) or 'NONE'}")
        self.logger.info(f"Phases: {', '.join(self.phases_to_run) or 'ALL'}")
        self.logger.info(f"Parallel: {self.parallel}")
        self.logger.info(f"Dry run: {self.dry_run}")
        self.logger.divider()

        if self.dry_run:
            return self._dry_run()

        if self.parallel and len(self.tracks_to_run) > 1:
            return self._run_parallel()
        else:
            return self._run_sequential()

    def _run_sequential(self) -> PipelineResult:
        """Run tracks one at a time."""
        for track_name in self.tracks_to_run:
            if track_name == "desktop" and not DESKTOP_AVAILABLE:
                self.logger.error("Desktop track unavailable — skipping")
                continue
            if track_name == "android" and not ANDROID_AVAILABLE:
                self.logger.error("Android track unavailable — skipping")
                continue

            self.logger.section(f"TRACK: {track_name.upper()}")
            track_result = self._run_single_track(track_name)
            self.result.tracks.append(track_result)

            status_color = {"passed": "GREEN", "failed": "RED", "skipped": "YELLOW"}.get(
                track_result.overall_status, "WHITE"
            )
            self.logger.info(
                f"Track {track_name}: {track_result.overall_status.upper()} "
                f"({len(track_result.phases)} phases)"
            )

        self.result.overall_status = self._aggregate_status()
        self.result.end_time = now_iso()
        return self.result

    def _run_parallel(self) -> PipelineResult:
        """Run tracks in parallel using ThreadPoolExecutor."""
        self.logger.info("Running tracks in parallel...")

        def run_track(name: str) -> TrackResult:
            if name == "desktop" and not DESKTOP_AVAILABLE:
                return TrackResult(track=name, overall_status="skipped")
            if name == "android" and not ANDROID_AVAILABLE:
                return TrackResult(track=name, overall_status="skipped")

            logger = Logger(LogLevel.INFO)
            if name == "desktop":
                return run_desktop_pipeline(
                    root=self.root,
                    config=self.config,
                    logger=logger,
                    phases_to_run=self.phases_to_run,
                )
            else:
                return run_android_pipeline(
                    root=self.root,
                    config=self.config,
                    logger=logger,
                    phases_to_run=self.phases_to_run,
                )

        with ThreadPoolExecutor(max_workers=len(self.tracks_to_run)) as executor:
            futures = {
                executor.submit(run_track, name): name
                for name in self.tracks_to_run
            }
            for future in as_completed(futures):
                track_name = futures[future]
                try:
                    track_result = future.result()
                    self.result.tracks.append(track_result)
                    self.logger.info(
                        f"Track {track_name}: {track_result.overall_status.upper()} "
                        f"({len(track_result.phases)} phases)"
                    )
                except Exception as e:
                    self.logger.error(f"Track {track_name} crashed: {e}")
                    self.result.tracks.append(TrackResult(
                        track=track_name,
                        overall_status="failed",
                        start_time=now_iso(),
                        end_time=now_iso(),
                    ))

        self.result.overall_status = self._aggregate_status()
        self.result.end_time = now_iso()
        return self.result

    def _run_single_track(self, track_name: str) -> TrackResult:
        """Run a single track."""
        if track_name == "desktop":
            logger = Logger(LogLevel.INFO)
            return run_desktop_pipeline(
                root=self.root,
                config=self.config,
                logger=logger,
                phases_to_run=self.phases_to_run,
            )
        elif track_name == "android":
            logger = Logger(LogLevel.INFO)
            return run_android_pipeline(
                root=self.root,
                config=self.config,
                logger=logger,
                phases_to_run=self.phases_to_run,
            )
        else:
            return TrackResult(
                track=track_name,
                overall_status="skipped",
                start_time=now_iso(),
                end_time=now_iso(),
            )

    def _dry_run(self) -> PipelineResult:
        """Show what would run without executing."""
        self.logger.info("── DRY RUN ──")
        self.logger.info(f"Tracks: {', '.join(self.tracks_to_run)}")
        self.logger.info(f"Phases: {', '.join(self.phases_to_run)}")
        for track in self.tracks_to_run:
            self.logger.info(f"  {track}:")
            for phase in self.phases_to_run:
                self.logger.info(f"    - {phase}")
        self.result.overall_status = "dry_run"
        self.result.end_time = now_iso()
        return self.result

    def _aggregate_status(self) -> str:
        """Determine overall pipeline status from track results."""
        statuses = [t.overall_status for t in self.result.tracks]
        if "failed" in statuses:
            return "failed"
        if "dry_run" in statuses:
            return "dry_run"
        if not statuses:
            return "no_tracks"
        if all(s == "passed" for s in statuses):
            return "passed"
        if all(s in ("passed", "skipped") for s in statuses):
            return "passed"
        return "mixed"


# ── Report generation ─────────────────────────────────────────────────────────


def generate_pipeline_reports(
    result: PipelineResult,
    report_dir: Path,
    output_formats: list[str] | None = None,
) -> None:
    """Generate text/JSON/YAML reports from a pipeline result."""
    output_formats = output_formats or ["text", "json", "yaml"]
    ensure_dir(report_dir)

    if "text" in output_formats:
        text_path = report_dir / "pipeline-report.txt"
        lines = format_pipeline_report(result)
        write_text_report(text_path, lines)
        print(f"\nText report: {text_path}")

    if "json" in output_formats:
        json_path = report_dir / "pipeline-report.json"
        write_json_report(json_path, serialize_pipeline_result(result))
        print(f"JSON report: {json_path}")

    if "yaml" in output_formats:
        yaml_path = report_dir / "pipeline-report.yaml"
        write_yaml_report(yaml_path, serialize_pipeline_result(result))
        print(f"YAML report: {yaml_path}")


def format_pipeline_report(result: PipelineResult) -> list[str]:
    """Format the full pipeline result as a human-readable text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  VM-Harness ON-DEVICE CI/CD PIPELINE — FULL REPORT")
    lines.append(f"  Generated: {result.start_time}")
    lines.append(f"  Overall Status: {result.overall_status.upper()}")
    lines.append(f"  Config: {len(result.config)} sections loaded")
    lines.append("=" * 70)
    lines.append("")

    for track_result in result.tracks:
        lines.append(f"━━━ {track_result.track.upper()} TRACK ━━━")
        lines.append(f"Status: {track_result.overall_status.upper()}")
        lines.append(f"Start: {track_result.start_time}")
        lines.append(f"End:   {track_result.end_time}")
        lines.append("")

        for phase in track_result.phases:
            phase_color = "GREEN" if phase.status == "passed" else (
                "RED" if phase.status == "failed" else "YELLOW"
            )
            lines.append(f"  [{phase_color}] {phase.phase.upper()}")
            lines.append(f"    Status: {phase.status}")
            lines.append(f"    Duration: {phase.duration_s:.1f}s")
            if phase.message:
                lines.append(f"    Message: {phase.message}")
            if phase.details:
                lines.append(f"    Details:")
                for key, val in phase.details.items():
                    if isinstance(val, dict):
                        lines.append(f"      {key}:")
                        for k, v in val.items():
                            if isinstance(v, (dict, list)):
                                lines.append(f"        {k}: {json.dumps(v)[:150]}")
                            else:
                                lines.append(f"        {k}: {v}")
                    else:
                        lines.append(f"      {key}: {val}")
            lines.append("")

    lines.append("=" * 70)
    lines.append(f"  END OF REPORT")
    lines.append("=" * 70)
    return lines


def serialize_pipeline_result(result: PipelineResult) -> dict[str, Any]:
    """Convert a PipelineResult to a JSON-serializable dict."""
    return {
        "overall_status": result.overall_status,
        "start_time": result.start_time,
        "end_time": result.end_time,
        "config_summary": {
            "desktop_enabled": result.config.get("desktop", {}).get("enabled", True),
            "android_enabled": result.config.get("android", {}).get("enabled", True),
            "fail_fast": result.config.get("global", {}).get("fail_fast", True),
        },
        "tracks": [
            {
                "track": t.track,
                "overall_status": t.overall_status,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "phases": [
                    {
                        "phase": p.phase,
                        "status": p.status,
                        "duration_s": p.duration_s,
                        "message": p.message,
                        "details": p.details,
                    }
                    for p in t.phases
                ],
            }
            for t in result.tracks
        ],
    }


# ── Main entry point ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="VM-Harness On-Device CI/CD Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ci/pipeline.py                          # Run all phases, both tracks
  python ci/pipeline.py --track desktop          # Desktop track only
  python ci/pipeline.py --track android          # Android track only
  python ci/pipeline.py --phase test             # Test phase only (all tracks)
  python ci/pipeline.py --phase build --track desktop  # Build desktop only
  python ci/pipeline.py --parallel              # Run tracks in parallel
  python ci/pipeline.py --dry-run               # Show what would run
  python ci/pipeline.py --log-level debug       # Verbose output
  python ci/pipeline.py --report-format text    # Text report only
        """,
    )

    parser.add_argument(
        "--track", "-t",
        action="append",
        choices=["desktop", "android", "all"],
        help="Track(s) to run (can be specified multiple times)",
    )
    parser.add_argument(
        "--phase", "-p",
        action="append",
        choices=["prepare", "preflight", "test", "build", "deploy", "all"],
        help="Phase(s) to run (can be specified multiple times)",
    )
    parser.add_argument(
        "--parallel", "-P",
        action="store_true",
        help="Run desktop and Android tracks in parallel",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would run without executing any commands",
    )
    parser.add_argument(
        "--log-level", "-l",
        default="info",
        choices=["debug", "info", "warn", "error"],
        help="Logging level (default: info)",
    )
    parser.add_argument(
        "--root", "-r",
        default=str(PROJECT_ROOT),
        help="Project root directory (default: project root)",
    )
    parser.add_argument(
        "--config", "-c",
        default=str(PROJECT_ROOT / "ci" / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Directory for reports (default: ci/report)",
    )
    parser.add_argument(
        "--report-format", "-o",
        default="all",
        choices=["text", "json", "yaml", "all"],
        help="Report format(s) to generate",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate reports from the last run's JSON report",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=None,
        help="Override config fail_fast setting",
    )

    args = parser.parse_args()

    # Setup
    root = Path(args.root).resolve()
    report_dir = ensure_dir(Path(args.report_dir) if args.report_dir else root / "ci" / "report")

    # Logger
    logger = Logger(LogLevel.from_str(args.log_level))

    # Load config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}")
        sys.exit(1)

    try:
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
        logger.info(f"Config loaded: {config_path}")
    except ImportError:
        logger.warn("PyYAML not available — using minimal config parser")
        from ci.common import _minimal_yaml_load
        config = _minimal_yaml_load(config_path)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Apply CLI overrides
    if args.fail_fast is not None:
        config.setdefault("global", {})["fail_fast"] = args.fail_fast

    # Determine tracks
    tracks = args.track or []
    if "all" in tracks:
        tracks = ["desktop", "android"]
    elif not tracks:
        tracks = ["desktop", "android"]

    # Determine phases
    phases = args.phase or []
    if "all" in phases:
        phases = ["prepare", "preflight", "test", "build", "deploy"]
    elif not phases:
        phases = ["prepare", "preflight", "test", "build", "deploy"]

    # Check availability
    available_tracks = []
    for t in tracks:
        if t == "desktop" and not DESKTOP_AVAILABLE:
            logger.error(f"Desktop track unavailable: {_DESKTOP_IMPORT_ERROR}")
        elif t == "android" and not ANDROID_AVAILABLE:
            logger.error(f"Android track unavailable: {_ANDROID_IMPORT_ERROR}")
        else:
            available_tracks.append(t)

    if not available_tracks:
        logger.error("No tracks available — cannot proceed")
        sys.exit(1)

    logger.info(f"Running tracks: {', '.join(available_tracks)}")
    logger.info(f"Running phases: {', '.join(phases)}")

    # Handle report-only mode
    if args.report_only:
        json_report = report_dir / "pipeline-report.json"
        if json_report.exists():
            with open(json_report) as f:
                data = json.load(f)
            result = deserialize_pipeline_result(data)
            generate_pipeline_reports(result, report_dir, [args.report_format])
            sys.exit(0)
        else:
            logger.error(f"No previous report found at {json_report}")
            sys.exit(1)

    # Run pipeline
    orchestrator = PipelineOrchestrator(
        root=root,
        config=config,
        logger=logger,
        tracks_to_run=available_tracks,
        phases_to_run=phases,
        parallel=args.parallel,
        dry_run=args.dry_run,
    )

    result = orchestrator.run()

    # Generate reports
    generate_pipeline_reports(result, report_dir, [args.report_format])

    # Summary
    status = result.overall_status.upper()
    logger.section(f"PIPELINE COMPLETE — STATUS: {status}")
    logger.info(f"Tracks run: {len(result.tracks)}")
    logger.info(f"Total duration: {result.end_time}")

    # Exit code
    if status == "PASSED":
        sys.exit(0)
    elif status in ("DRY_RUN", "NO_TRACKS", "MIXED"):
        sys.exit(0)
    else:
        sys.exit(1)


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


if __name__ == "__main__":
    main()
