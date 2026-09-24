"""VM Cloner and Template System for VM-Harness.

Provides:
- VMCloner class for linked clones (qemu-img create -f qcow2 -b base -F qcow2 new)
  and full clones (qemu-img convert)
- Template system: save VM config as JSON, clone from template
- Template metadata: name, description, OS, RAM, CPU, date created
- Clone dialog integrated into VM Switcher
- Template management UI
- Templates stored in PROJECT_DIR/.templates/
- Progress reporting via QThread signals

Usage:
    from gui.vm_cloner import VMCloner, TemplateManager, CloneDialog, TemplateManagerDialog

    cloner = VMCloner(qemu_img_path=r"C:\Program Files\qemu\qemu-img.exe")
    cloner.linked_clone(base_path, new_path)
    cloner.full_clone(source_path, dest_path)

    templates = TemplateManager()
    templates.save_template(vm_config)
    template_list = templates.list_templates()
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
n# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QFormLayout, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QProgressBar,
    QGroupBox, QSplitter, QWidget, QInputDialog, QFrame,
    QSpinBox, QCheckBox, QGridLayout, QSizePolicy,
)

from gui.theme import T, progress_style
from gui.widgets import Card

# Paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_DIR / ".templates"
QEMU_IMG_DEFAULT = r"C:\Program Files\qemu\qemu-img.exe"


# ═══════════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TemplateMetadata:
    """Metadata stored with each template."""
    name: str
    description: str = ""
    os_type: str = "linux"          # linux, windows, bsd, other
    ram_mb: int = 4096
    cpus: int = 2
    disk_format: str = "qcow2"
    date_created: str = ""
    date_updated: str = ""
    source_vm: str = ""             # original VM name
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now().isoformat(timespec="seconds")
        if not self.date_created:
            self.date_created = now
        if not self.date_updated:
            self.date_updated = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "os_type": self.os_type,
            "ram_mb": self.ram_mb,
            "cpus": self.cpus,
            "disk_format": self.disk_format,
            "date_created": self.date_created,
            "date_updated": self.date_updated,
            "source_vm": self.source_vm,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemplateMetadata:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════════════════
# Clone Worker Thread
# ═══════════════════════════════════════════════════════════════════════════════

class CloneWorker(QThread):
    """Background worker for VM cloning operations.

    Signals:
        progress(int, str): percentage and message
        finished_ok(str): path of created disk on success
        failed(str): error message on failure
    """

    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        qemu_img: str,
        operation: str,  # "linked" or "full"
        source: str,
        dest: str,
        disk_format: str = "qcow2",
    ):
        super().__init__()
        self._qemu_img = qemu_img
        self._operation = operation
        self._source = source
        self._dest = dest
        self._disk_format = disk_format

    def run(self):
        try:
            self.progress.emit(5, f"Preparing {self._operation} clone...")

            if not os.path.exists(self._source):
                self.failed.emit(f"Source disk not found: {self._source}")
                return

            dest_path = Path(self._dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if self._operation == "linked":
                self._do_linked_clone()
            elif self._operation == "full":
                self._do_full_clone()
            else:
                self.failed.emit(f"Unknown operation: {self._operation}")
                return

            self.progress.emit(100, "Clone complete")
            if os.path.exists(self._dest):
                self.finished_ok.emit(self._dest)
            else:
                self.failed.emit("Output file was not created")

        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
            self.failed.emit(f"qemu-img failed: {stderr}")
        except Exception as e:
            self.failed.emit(str(e))

    def _do_linked_clone(self):
        """Create a qcow2 backing-file clone (linked/overlay clone)."""
        self.progress.emit(10, "Creating linked clone (backing file)...")
        cmd = [
            self._qemu_img, "create",
            "-f", self._disk_format,
            "-b", self._source,
            "-F", self._disk_format,
            self._dest,
        ]
        self.progress.emit(20, "Running qemu-img create...")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd,
                output=result.stdout.encode(),
                stderr=result.stderr.encode(),
            )
        # Get info to verify
        self.progress.emit(90, "Verifying clone...")
        info_cmd = [self._qemu_img, "info", self._dest]
        subprocess.run(info_cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)

    def _do_full_clone(self):
        """Create a full independent clone (convert)."""
        self.progress.emit(10, "Starting full clone (convert)...")

        # Get source size for progress estimation
        source_size = os.path.getsize(self._source)
        self.progress.emit(15, f"Source size: {source_size / (1024**2):.1f} MB")

        cmd = [
            self._qemu_img, "convert",
            "-f", self._disk_format,
            "-O", self._disk_format,
            "-p",  # progress
            self._source,
            self._dest,
        ]
        self.progress.emit(20, "Running qemu-img convert...")

        # Run with progress parsing
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )

        # Parse progress from stdout
        last_pct = 20
        for line in process.stdout:
            line = line.strip()
            if "%" in line:
                # Parse percentage from qemu-img -p output
                try:
                    pct_str = line.split("(")[1].split("%")[0]
                    pct = int(float(pct_str))
                    # Map 0-100 to 20-95
                    mapped = 20 + int(pct * 0.75)
                    if mapped > last_pct:
                        last_pct = mapped
                        self.progress.emit(last_pct, f"Converting... {pct}%")
                except (IndexError, ValueError):
                    pass

        process.wait(timeout=600)
        if process.returncode != 0:
            self.failed.emit(f"Convert failed with code {process.returncode}")
            return

        self.progress.emit(95, "Verifying full clone...")


# ═══════════════════════════════════════════════════════════════════════════════
# VMCloner Class
# ═══════════════════════════════════════════════════════════════════════════════

class VMCloner:
    """High-level VM cloning operations.

    Wraps qemu-img commands for linked and full clones.
    Optionally emits progress via callback.
    """

    def __init__(
        self,
        qemu_img_path: str = QEMU_IMG_DEFAULT,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        self._qemu_img = qemu_img_path
        self._progress_cb = progress_callback or (lambda pct, msg: None)
        self._worker: Optional[CloneWorker] = None

    @property
    def qemu_img(self) -> str:
        return self._qemu_img

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def linked_clone(
        self,
        base_path: str,
        new_path: str,
        disk_format: str = "qcow2",
        blocking: bool = False,
    ) -> tuple[bool, str]:
        """Create a linked clone (backing file clone).

        Args:
            base_path: Path to the base qcow2 image.
            new_path: Path for the new overlay image.
            disk_format: Disk format (default qcow2).
            blocking: If True, run synchronously.

        Returns:
            (success, message_or_path)
        """
        if blocking:
            return self._linked_clone_sync(base_path, new_path, disk_format)
        else:
            self._run_worker("linked", base_path, new_path, disk_format)
            return True, "Clone started in background"

    def full_clone(
        self,
        source_path: str,
        dest_path: str,
        disk_format: str = "qcow2",
        blocking: bool = False,
    ) -> tuple[bool, str]:
        """Create a full independent clone.

        Args:
            source_path: Path to the source image.
            dest_path: Path for the new image.
            disk_format: Disk format (default qcow2).
            blocking: If True, run synchronously.

        Returns:
            (success, message_or_path)
        """
        if blocking:
            return self._full_clone_sync(source_path, dest_path, disk_format)
        else:
            self._run_worker("full", source_path, dest_path, disk_format)
            return True, "Clone started in background"

    def _run_worker(self, operation: str, source: str, dest: str, disk_format: str):
        """Start a background clone worker thread."""
        if self.is_running:
            raise RuntimeError("A clone operation is already in progress")
        self._worker = CloneWorker(self._qemu_img, operation, source, dest, disk_format)
        self._worker.progress.connect(self._progress_cb)
        self._worker.start()

    def connect_signals(
        self,
        on_progress: Callable[[int, str], None],
        on_finished: Callable[[str], None],
        on_failed: Callable[[str], None],
    ):
        """Connect callbacks for async clone operations."""
        self._worker = getattr(self, "_worker", None)
        # Store for later connection when worker is created
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_failed = on_failed

    def _ensure_worker_connected(self):
        """Connect stored callbacks to current worker if available."""
        worker = getattr(self, "_worker", None)
        if worker is None:
            return
        if hasattr(self, "_on_progress"):
            try:
                worker.progress.connect(self._on_progress)
            except (AttributeError, RuntimeError):
                pass  # Signal/slot not available
        if hasattr(self, "_on_finished"):
            try:
                worker.finished_ok.connect(self._on_finished)
            except (AttributeError, RuntimeError):
                pass  # Signal/slot not available
        if hasattr(self, "_on_failed"):
            try:
                worker.failed.connect(self._on_failed)
            except (AttributeError, RuntimeError):
                pass

    def _linked_clone_sync(
        self, base_path: str, new_path: str, disk_format: str
    ) -> tuple[bool, str]:
        """Synchronous linked clone."""
        self._progress_cb(5, "Preparing linked clone...")
        if not os.path.exists(base_path):
            return False, f"Base image not found: {base_path}"

        Path(new_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._qemu_img, "create",
            "-f", disk_format,
            "-b", base_path,
            "-F", disk_format,
            new_path,
        ]
        self._progress_cb(20, "Creating overlay...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return False, f"qemu-img error: {result.stderr}"
        self._progress_cb(100, "Done")
        return True, new_path

    def _full_clone_sync(
        self, source_path: str, dest_path: str, disk_format: str
    ) -> tuple[bool, str]:
        """Synchronous full clone."""
        self._progress_cb(5, "Preparing full clone...")
        if not os.path.exists(source_path):
            return False, f"Source image not found: {source_path}"

        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._qemu_img, "convert",
            "-f", disk_format,
            "-O", disk_format,
            source_path,
            dest_path,
        ]
        self._progress_cb(20, "Converting...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return False, f"qemu-img error: {result.stderr}"
        self._progress_cb(100, "Done")
        return True, dest_path

    def get_disk_info(self, disk_path: str) -> dict[str, Any]:
        """Get disk image info via qemu-img info."""
        cmd = [self._qemu_img, "info", "--output=json", disk_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return {"error": result.stderr}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout}


# ═══════════════════════════════════════════════════════════════════════════════
# Template Manager
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateManager:
    """Manage VM templates stored as JSON in PROJECT_DIR/.templates/."""

    def __init__(self, templates_dir: str | Path = TEMPLATES_DIR):
        self._dir = Path(templates_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def templates_dir(self) -> Path:
        return self._dir

    def save_template(
        self,
        name: str,
        vm_config: dict[str, Any],
        metadata: Optional[TemplateMetadata] = None,
        description: str = "",
        os_type: str = "linux",
        ram_mb: int = 4096,
        cpus: int = 2,
        tags: Optional[list[str]] = None,
    ) -> Path:
        """Save a VM configuration as a template.

        Args:
            name: Template name (used as filename).
            vm_config: VM configuration dictionary.
            metadata: Optional pre-built metadata.
            description: Template description.
            os_type: OS type (linux, windows, bsd, other).
            ram_mb: RAM allocation.
            cpus: CPU count.
            tags: Optional tags list.

        Returns:
            Path to the saved template file.
        """
        template = {
            "metadata": None,
            "vm_config": vm_config,
        }

        if metadata is None:
            metadata = TemplateMetadata(
                name=name,
                description=description,
                os_type=os_type,
                ram_mb=ram_mb,
                cpus=cpus,
                source_vm=vm_config.get("vm_name", ""),
                tags=tags or [],
            )

        template["metadata"] = metadata.to_dict()

        filepath = self._dir / f"{name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
        return filepath

    def load_template(self, name: str) -> dict[str, Any]:
        """Load a template by name."""
        filepath = self._dir / f"{name}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Template not found: {name}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_templates(self) -> list[TemplateMetadata]:
        """List all available templates."""
        templates = []
        for filepath in sorted(self._dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                meta = TemplateMetadata.from_dict(data.get("metadata", {}))
                # Ensure name comes from filename if missing
                if not meta.name:
                    meta.name = filepath.stem
                templates.append(meta)
            except (OSError, json.JSONDecodeError, ValueError):
                continue  # Corrupt template file — skip
        return templates

    def get_template(self, name: str) -> tuple[TemplateMetadata, dict[str, Any]]:
        """Get template metadata and VM config."""
        data = self.load_template(name)
        meta = TemplateMetadata.from_dict(data.get("metadata", {}))
        return meta, data["vm_config"]

    def delete_template(self, name: str) -> bool:
        """Delete a template by name."""
        filepath = self._dir / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def template_exists(self, name: str) -> bool:
        """Check if a template exists."""
        return (self._dir / f"{name}.json").exists()

    def update_metadata(self, name: str, **kwargs) -> bool:
        """Update template metadata fields."""
        try:
            data = self.load_template(name)
            meta = data.get("metadata", {})
            meta.update(kwargs)
            meta["date_updated"] = datetime.now().isoformat(timespec="seconds")
            data["metadata"] = meta
            filepath = self._dir / f"{name}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except (OSError, json.JSONDecodeError):
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# Clone Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class CloneDialog(QDialog):
    """Dialog for cloning VMs or creating from templates."""

    def __init__(
        self,
        parent=None,
        source_disk: str = "",
        template_manager: Optional[TemplateManager] = None,
        qemu_img: str = QEMU_IMG_DEFAULT,
    ):
        super().__init__(parent)
        self.setWindowTitle("Clone VM / Create from Template")
        self.setMinimumSize(550, 500)
        self.setStyleSheet(
            f"QDialog {{ background: {T.BG_PRIMARY}; }}"
            f"QLabel {{ color: {T.TEXT_PRIMARY}; }}"
        )

        self._source_disk = source_disk
        self._tm = template_manager or TemplateManager()
        self._qemu_img = qemu_img
        self._cloner = VMCloner(qemu_img, self._on_progress)
        self._result_path: str = ""

        self._setup_ui()
        self._load_templates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Mode Selection ─────────────────────────────────────────────────────
        mode_group = QGroupBox("Clone Mode")
        mode_group.setStyleSheet(
            f"QGroupBox {{ color: {T.TEXT_SECONDARY}; font-size: 11px; "
            f"border: 1px solid {T.BG_TERTIARY}; border-radius: 6px; margin-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
        )
        mode_layout = QHBoxLayout(mode_group)

        self._mode_linked = QCheckBox("Linked Clone")
        self._mode_linked.setChecked(True)
        self._mode_linked.setStyleSheet(f"color: {T.TEXT_PRIMARY};")
        self._mode_full = QCheckBox("Full Clone")
        self._mode_full.setStyleSheet(f"color: {T.TEXT_PRIMARY};")

        self._mode_linked.toggled.connect(lambda: self._mode_full.setChecked(False) if self._mode_linked.isChecked() else None)
        self._mode_full.toggled.connect(lambda: self._mode_linked.setChecked(False) if self._mode_full.isChecked() else None)

        mode_layout.addWidget(self._mode_linked)
        mode_layout.addWidget(self._mode_full)
        mode_layout.addStretch()
        layout.addWidget(mode_group)

        # ── Source / Template ──────────────────────────────────────────────────
        source_group = QGroupBox("Source")
        source_group.setStyleSheet(
            f"QGroupBox {{ color: {T.TEXT_SECONDARY}; font-size: 11px; "
            f"border: 1px solid {T.BG_TERTIARY}; border-radius: 6px; margin-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
        )
        source_layout = QFormLayout(source_group)

        # Template selector
        template_row = QHBoxLayout()
        self._template_combo = QComboBox()
        self._template_combo.setStyleSheet(
            f"QComboBox {{ background: {T.BG_PRIMARY}; color: {T.TEXT_PRIMARY}; }}"
        )
        self._template_combo.currentTextChanged.connect(self._on_template_selected)
        template_row.addWidget(self._template_combo)

        load_template_btn = QPushButton("Load Template")
        load_template_btn.setFixedSize(100, 24)
        load_template_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BRAND}; color: white; border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: {T.BRAND_HOVER}; }}"
        )
        load_template_btn.clicked.connect(self._load_template_config)
        template_row.addWidget(load_template_btn)
        source_layout.addRow("Template:", template_row)

        # Source disk
        disk_row = QHBoxLayout()
        self._source_edit = QLineEdit(self._source_disk)
        self._source_edit.setPlaceholderText("Path to source disk image...")
        self._source_edit.setStyleSheet(
            f"QLineEdit {{ background: {T.BG_PRIMARY}; color: {T.TEXT_PRIMARY}; }}"
        )
        disk_row.addWidget(self._source_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.setFixedSize(70, 24)
        browse_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_SECONDARY}; color: {T.TEXT_SECONDARY}; }}"
        )
        browse_btn.clicked.connect(self._browse_source)
        disk_row.addWidget(browse_btn)
        source_layout.addRow("Source Disk:", disk_row)

        # Destination disk
        dest_row = QHBoxLayout()
        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("Path for new disk image...")
        self._dest_edit.setStyleSheet(
            f"QLineEdit {{ background: {T.BG_PRIMARY}; color: {T.TEXT_PRIMARY}; }}"
        )
        dest_row.addWidget(self._dest_edit)

        dest_browse_btn = QPushButton("Browse...")
        dest_browse_btn.setFixedSize(70, 24)
        dest_browse_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_SECONDARY}; color: {T.TEXT_SECONDARY}; }}"
        )
        dest_browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(dest_browse_btn)
        source_layout.addRow("Dest Disk:", dest_row)

        layout.addWidget(source_group)

        # ── Clone Settings ─────────────────────────────────────────────────────
        settings_group = QGroupBox("VM Settings")
        settings_group.setStyleSheet(
            f"QGroupBox {{ color: {T.TEXT_SECONDARY}; font-size: 11px; "
            f"border: 1px solid {T.BG_TERTIARY}; border-radius: 6px; margin-top: 8px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}"
        )
        settings_layout = QFormLayout(settings_group)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("New VM name...")
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: {T.BG_PRIMARY}; color: {T.TEXT_PRIMARY}; }}"
        )
        settings_layout.addRow("VM Name:", self._name_edit)

        self._ram_spin = QSpinBox()
        self._ram_spin.setRange(256, 131072)
        self._ram_spin.setValue(4096)
        self._ram_spin.setSingleStep(512)
        settings_layout.addRow("RAM (MB):", self._ram_spin)

        self._cpu_spin = QSpinBox()
        self._cpu_spin.setRange(1, 64)
        self._cpu_spin.setValue(2)
        settings_layout.addRow("vCPUs:", self._cpu_spin)

        layout.addWidget(settings_group)

        # ── Progress ───────────────────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(progress_style())
        self._progress_bar.setFixedHeight(20)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._clone_btn = QPushButton("Clone")
        self._clone_btn.setFixedSize(100, 32)
        self._clone_btn.setStyleSheet(
            f"QPushButton {{ background: {T.STATUS_RUNNING}; color: white; "
            f"border: none; border-radius: 6px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #16a34a; }}"
        )
        self._clone_btn.clicked.connect(self._start_clone)
        btn_row.addWidget(self._clone_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: {T.STATUS_STOPPED}; color: white; "
            f"border: none; border-radius: 6px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #dc2626; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _load_templates(self):
        """Load template list into combo box."""
        self._template_combo.clear()
        self._template_combo.addItem("-- Select Template --")
        templates = self._tm.list_templates()
        for tmpl in templates:
            self._template_combo.addItem(tmpl.name)

    def _on_template_selected(self, name: str):
        """Handle template selection."""
        if not name or name.startswith("--"):
            return
        self._load_template_config()

    def _load_template_config(self):
        """Load configuration from selected template."""
        name = self._template_combo.currentText()
        if not name or name.startswith("--"):
            return
        try:
            meta, vm_config = self._tm.get_template(name)
            self._name_edit.setText(vm_config.get("vm_name", meta.name))
            self._ram_spin.setValue(meta.ram_mb)
            self._cpu_spin.setValue(meta.cpus)
            if vm_config.get("disk_path"):
                self._source_edit.setText(vm_config["disk_path"])
            self._status_label.setText(f"Loaded template: {name}")
        except Exception as e:
            self._status_label.setText(f"Error loading template: {e}")

    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Source Disk", "",
            "Disk Images (*.qcow2 *.img *.vmdk *.raw);;All Files (*)"
        )
        if path:
            self._source_edit.setText(path)

    def _browse_dest(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Destination Disk", "",
            "QCOW2 (*.qcow2);;All Files (*)"
        )
        if path:
            self._dest_edit.setText(path)

    def _on_progress(self, pct: int, msg: str):
        """Update progress bar."""
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)

    def _start_clone(self):
        """Start the clone operation."""
        source = self._source_edit.text().strip()
        dest = self._dest_edit.text().strip()

        if not source:
            QMessageBox.warning(self, "Error", "Select a source disk")
            return
        if not dest:
            QMessageBox.warning(self, "Error", "Select a destination path")
            return
        if not os.path.exists(source):
            QMessageBox.warning(self, "Error", f"Source not found: {source}")
            return

        self._clone_btn.setEnabled(False)
        self._progress_bar.setValue(0)

        if self._mode_full.isChecked():
            self._cloner._run_worker("full", source, dest)
        else:
            self._cloner._run_worker("linked", source, dest)

        # Connect signals for this operation
        worker = self._cloner._worker
        if worker:
            worker.progress.connect(self._on_progress)
            worker.finished_ok.connect(self._on_clone_finished)
            worker.failed.connect(self._on_clone_failed)

    def _on_clone_finished(self, path: str):
        self._result_path = path
        self._status_label.setText(f"Clone complete: {path}")
        self._clone_btn.setEnabled(True)
        QMessageBox.information(self, "Success", f"Clone created:\n{path}")
        self.accept()

    def _on_clone_failed(self, msg: str):
        self._status_label.setText(f"Failed: {msg}")
        self._clone_btn.setEnabled(True)
        QMessageBox.critical(self, "Clone Failed", msg)

    @property
    def result_path(self) -> str:
        return self._result_path


# ═══════════════════════════════════════════════════════════════════════════════
# Template Manager Dialog
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateManagerDialog(QDialog):
    """Dialog for managing VM templates."""

    def __init__(
        self,
        parent=None,
        template_manager: Optional[TemplateManager] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Template Manager")
        self.setMinimumSize(700, 450)
        self.setStyleSheet(
            f"QDialog {{ background: {T.BG_PRIMARY}; }}"
            f"QLabel {{ color: {T.TEXT_PRIMARY}; }}"
        )

        self._tm = template_manager or TemplateManager()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Template List ──────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel("Templates")
        list_label.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; text-transform: uppercase;"
        )
        left_layout.addWidget(list_label)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {T.BG_SECONDARY}; color: {T.TEXT_PRIMARY}; }}"
            f"QListWidget::item {{ padding: 8px; }}"
            f"QListWidget::item:selected {{ background: {T.BRAND}; }}"
        )
        self._list.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list)

        splitter.addWidget(left_widget)

        # Right: details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_label = QLabel("Template Details")
        details_label.setStyleSheet(
            f"color: {T.TEXT_SECONDARY}; font-size: 11px; font-weight: 600; text-transform: uppercase;"
        )
        right_layout.addWidget(details_label)

        self._details = QTextEdit()
        self._details.setReadOnly(True)
        self._details.setStyleSheet(
            f"QTextEdit {{ background: {T.BG_SECONDARY}; color: {T.TEXT_PRIMARY}; }}"
        )
        right_layout.addWidget(self._details)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        new_btn = QPushButton("New from VM...")
        new_btn.setFixedSize(110, 32)
        new_btn.setStyleSheet(
            f"QPushButton {{ background: {T.STATUS_RUNNING}; color: white; "
            f"border: none; border-radius: 6px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #16a34a; }}"
        )
        new_btn.clicked.connect(self._create_template)
        btn_row.addWidget(new_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(60, 32)
        edit_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BRAND}; color: white; "
            f"border: none; border-radius: 6px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {T.BRAND_HOVER}; }}"
        )
        edit_btn.clicked.connect(self._edit_template)
        btn_row.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setFixedSize(70, 32)
        delete_btn.setStyleSheet(
            f"QPushButton {{ background: {T.STATUS_STOPPED}; color: white; "
            f"border: none; border-radius: 6px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #dc2626; }}"
        )
        delete_btn.clicked.connect(self._delete_template)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(70, 32)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_SECONDARY}; color: {T.TEXT_SECONDARY}; }}"
        )
        refresh_btn.clicked.connect(self._refresh_list)
        btn_row.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(70, 32)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_SECONDARY}; color: {T.TEXT_SECONDARY}; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _refresh_list(self):
        """Refresh template list."""
        self._list.clear()
        templates = self._tm.list_templates()
        for tmpl in templates:
            item = QListWidgetItem(tmpl.name)
            item.setData(Qt.UserRole, tmpl.name)
            self._list.addItem(item)

    def _on_selection_changed(self, current, _previous):
        """Update details panel."""
        if not current:
            self._details.clear()
            return
        name = current.data(Qt.UserRole)
        try:
            meta, vm_config = self._tm.get_template(name)
            text = (
                f"<b>{meta.name}</b><br>"
                f"<br>"
                f"<b>Description:</b> {meta.description or '—'}<br>"
                f"<b>OS:</b> {meta.os_type}<br>"
                f"<b>RAM:</b> {meta.ram_mb} MB<br>"
                f"<b>vCPUs:</b> {meta.cpus}<br>"
                f"<b>Disk Format:</b> {meta.disk_format}<br>"
                f"<b>Created:</b> {meta.date_created}<br>"
                f"<b>Updated:</b> {meta.date_updated}<br>"
                f"<b>Source VM:</b> {meta.source_vm or '—'}<br>"
                f"<b>Tags:</b> {', '.join(meta.tags) if meta.tags else '—'}<br>"
                f"<br>"
                f"<b>VM Config:</b><br>"
            )
            text += json.dumps(vm_config, indent=2).replace("\n", "<br>").replace(" ", "&nbsp;")
            self._details.setHtml(text)
        except Exception as e:
            self._details.setPlainText(f"Error: {e}")

    def _create_template(self):
        """Create a new template from user input."""
        name, ok = QInputDialog.getText(self, "New Template", "Template name:")
        if not ok or not name.strip():
            return

        # Gather metadata
        desc, ok = QInputDialog.getText(self, "Description", "Description:")
        if not ok:
            return

        os_type, ok = QInputDialog.getItem(
            self, "OS Type", "Operating System:",
            ["linux", "windows", "bsd", "other"], 0, False
        )
        if not ok:
            return

        ram, ok = QInputDialog.getInt(self, "RAM", "RAM (MB):", 4096, 256, 131072, 512)
        if not ok:
            return

        cpus, ok = QInputDialog.getInt(self, "CPUs", "vCPUs:", 2, 1, 64, 1)
        if not ok:
            return

        # Build a minimal VM config
        vm_config = {
            "vm_name": name.strip(),
            "description": desc,
            "ram_mb": ram,
            "cpus": cpus,
            "qemu_binary": r"C:\Program Files\qemu\qemu-system-x86_64.exe",
            "display": "sdl",
        }

        self._tm.save_template(
            name=name.strip(),
            vm_config=vm_config,
            description=desc,
            os_type=os_type,
            ram_mb=ram,
            cpus=cpus,
        )
        self._refresh_list()

    def _edit_template(self):
        """Edit selected template metadata."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a template first")
            return
        name = item.data(Qt.UserRole)

        try:
            meta, _ = self._tm.get_template(name)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        new_desc, ok = QInputDialog.getText(
            self, "Edit Description", "Description:",
            QLineEdit.Normal, meta.description
        )
        if ok:
            self._tm.update_metadata(name, description=new_desc)
            self._refresh_list()

    def _delete_template(self):
        """Delete selected template."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a template first")
            return
        name = item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete template '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._tm.delete_template(name)
            self._refresh_list()
