# VM-Harness Architecture

> **Version:** 2.0.0  
> **Last Updated:** 2026-09-23  
> **Platform:** Windows (primary), Linux, macOS (partial)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Panel Lifecycle](#2-panel-lifecycle)
3. [Async Adapter Pattern](#3-async-adapter-pattern)
4. [Backend Abstraction Layer](#4-backend-abstraction-layer)
5. [Streaming Bridge Protocol](#5-streaming-bridge-protocol)
6. [REST API Surface](#6-rest-api-surface)
7. [Single-Instance Lock Mechanism](#7-single-instance-lock-mechanism)
8. [Resilience System](#8-resilience-system)
9. [TLS/SSL Setup](#9-tlsssl-setup)
10. [Plugin API Design (Proposed)](#10-plugin-api-design-proposed)
11. [Directory Structure](#11-directory-structure)

---

## 1. System Overview

VM-Harness is a desktop application for managing virtual machines (QEMU, VMware, VirtualBox, WSL, Hyper-V, KVM), containers (Docker, Podman), and Kubernetes clusters from a unified PyQt5 GUI. It provides:

- A **GUI application** (PyQt5, frameless window, dark theme)
- A **headless REST API server** (aiohttp, port 8443, TLS-enabled)
- A **streaming bridge** (WebSocket, port 8445, for remote desktop/input)
- A **QMP bridge** (async QMP client → PyQt5 signals)
- An **SSH bridge** (async SSH client → PyQt5 signals)
- Full **resilience system** (crash recovery, hot reload, failover, health checks)

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VM-Harness Application                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   PyQt5 GUI  │  │  Headless    │  │    Streaming Bridge      │  │
│  │  (main_window)│  │  REST API    │  │   (WebSocket :8445)      │  │
│  │  Port N/A    │  │  (aiohttp)   │  │  Frame capture + input   │  │
│  │              │  │  Port 8443   │  │  injection               │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                  │                      │                  │
│         ▼                  ▼                      ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Bridge Layer (Signals)                     │   │
│  │  QMPBridge  │  SSHBridge  │  MultiVMQMPBridge               │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │                  AsyncAdapter (Singleton)                     │   │
│  │         Bridges async backends → sync GUI calls              │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │              Backend Abstraction Layer                        │   │
│  │  ┌─────────────────┐  ┌──────────────────────────────────┐   │   │
│  │  │ContainerBackend │  │     HypervisorBackend (ABC)       │   │   │
│  │  │  (ABC)          │  │  QEMU │ VMware │ VBox │ WSL │ ...│   │   │
│  │  │  Docker         │  │  Hyper-V │ KVM                    │   │   │
│  │  │  Kubernetes     │  │                                  │   │   │
│  │  │  Podman         │  │  VMConfig / VMStatus / VMMetrics│   │   │
│  │  └─────────────────┘  └──────────────────────────────────┘   │   │
│  │              HypervisorRegistry (auto-detect)                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Resilience System                           │   │
│  │  CrashHandler │ AtomicState │ ProcessGuardian │ HotReloader  │   │
│  │  FailoverManager │ HealthChecker │ SelfHealingOrchestrator    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Security & Middleware                            │   │
│  │  Auth (API keys) │ RBAC │ Rate Limiting │ TLS/SSL             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Panel Lifecycle

### 2.1 Registration

Panels are registered in `MainWindow._build_panels()` (`gui/main_window.py`). Each panel is a `(PanelClass, panel_name)` tuple in an ordered list:

```python
panel_list = [
    (DashboardPanel, "dashboard"),
    (VMSwitcherPanel, "vm_switcher"),
    (VMControlPanel, "vm_control"),
    (GuestTerminalPanel, "guest_terminal"),
    (GuestAgentPanel, "guest_agent"),
    (TelemetryPanel, "telemetry"),
    (QMPConsolePanel, "qmp_console"),
    (QemuSystemInfoPanel, "sysinfo"),
    (SnapshotPanel, "snapshots"),
    (ISOManagerPanel, "iso"),
    (VMCreationWizard, "wizard"),
    (StoragePanel, "storage"),
    (USBDevicePanel, "usb"),
    (NetworkPanel, "network"),
    (CPUControlPanel, "cpu"),
    (DisplayPanel, "display"),
    (AdvancedQEmuPanel, "qemu"),
    (AutomationPanel, "automation"),
    (TroubleshootPanel, "troubleshoot"),
    (ChatPanel, "chat"),
    (AIProvidersPanel, "providers"),
    (MonitoringPanel, "monitoring"),
    (SettingsPanel, "settings"),
    (PairingPanel, "pairing"),
    (SecurityPanel, "security"),
    (LogsPanel, "logs"),
    (ContainerPanel, "containers"),
    (ContainerTerminalPanel, "container_terminal"),
    (ContainerStatsPanel, "container_stats"),
    (KubernetesEditorPanel, "k8s_editor"),
    (KubernetesTreePanel, "k8s_tree"),
    (VMwareVBoxPanel, "vmware_vbox"),
]
```

### 2.2 Instantiation

All panels are instantiated eagerly during `MainWindow.__init__()`:

```python
self.panels: dict[str, QWidget] = {}

for panel_cls, name in panel_list:
    panel = panel_cls(self)          # Instantiate with MainWindow as parent
    self.panels[name] = panel         # Store in dict
    self.panel_stack.addWidget(panel) # Add to QStackedWidget
```

Panels are `QWidget` subclasses. Each panel receives the `MainWindow` as its Qt parent, enabling:
- Access to shared bridges (`qmp_bridge`, `ssh_bridge`)
- Signal/slot connections back to the main window
- Consistent theming via `gui.theme.T`

### 2.3 Panel Switching

The sidebar (`Sidebar` widget) emits `current_panel_changed(str)` when the user clicks a navigation item. `MainWindow._switch_panel()` handles the transition:

```python
def _switch_panel(self, name: str):
    if name in self.panels:
        self.panel_stack.setCurrentWidget(self.panels[name])
        self.status_label.setText(f"Panel: {name.replace('_', ' ').title()}")
```

`QStackedWidget` ensures only one panel is visible at a time, but all panels remain in memory.

### 2.4 Bridge Wiring

After panel instantiation, bridges are connected to panels that need them:

```python
# QMP bridge → panels that display VM status
self.panels["dashboard"].set_qmp_bridge(self.qmp_bridge)
self.panels["vm_control"].set_multi_qmp_bridge(self.qmp_bridge)
self.panels["guest_agent"].set_qmp_bridge(self.qmp_bridge)
self.panels["telemetry"].set_qmp_bridge(self.qmp_bridge)
self.panels["qmp_console"].set_qmp_bridge(self.qmp_bridge)

# SSH bridge → panels that interact with the guest OS
self.panels["guest_terminal"].set_ssh_bridge(self.ssh_bridge)
self.panels["guest_agent"].set_ssh_bridge(self.ssh_bridge)
self.panels["telemetry"].set_ssh_bridge(self.ssh_bridge)
```

### 2.5 Panel Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Panel Lifecycle                       │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │ Register │───▶│ Instantiate│──▶│ Add to StackedWidget│ │
│  │ (list)   │    │ (new)    │    │                  │  │
│  └──────────┘    └──────────┘    └────────┬─────────┘  │
│                                           │             │
│                                           ▼             │
│                                  ┌────────────────┐     │
│                                  │ Wire Bridges   │     │
│                                  │ (QMP/SSH)      │     │
│                                  └────────┬───────┘     │
│                                           │             │
│              ┌────────────────────────────┼────────┐    │
│              │                            │        │    │
│              ▼                            ▼        │    │
│     ┌──────────────┐            ┌──────────────┐   │    │
│     │   Visible    │◀──switch──▶│   Hidden     │   │    │
│     │ (current)    │            │ (stacked)    │   │    │
│     └──────────────┘            └──────────────┘   │    │
│                                                     │    │
│     ┌───────────────────────────────────────────────┘    │
│     │  Destroy (on app close — Qt parent-child cleanup)  │
│     └────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────┘
```

### 2.6 Panel Communication Pattern

Panels communicate with the rest of the application through:

1. **Direct bridge access** — panels call methods on `QMPBridge`/`SSHBridge` which emit PyQt5 signals
2. **REST API calls** — panels use `urllib.request` to call the local REST API at `http://127.0.0.1:8443`
3. **Qt signals/slots** — panels connect to bridge signals (e.g., `bridge.vm_status.connect(panel._on_vm_status)`)

---

## 3. Async Adapter Pattern

### 3.1 Problem

All backend methods (`ContainerBackend`, `HypervisorBackend`) are `async` to support non-blocking I/O. However, the PyQt5 GUI runs on a synchronous main thread and cannot `await` coroutines.

### 3.2 Solution: AsyncAdapter Singleton

`gui/async_adapter.py` provides `AsyncAdapter`, a thread-safe singleton that bridges async backends to synchronous GUI calls.

```python
from gui.async_adapter import get_adapter

adapter = get_adapter()
containers = adapter.docker.list_containers()      # Sync call, async under the hood
adapter.qemu.start_vm("my-vm")                     # Blocking until result
```

### 3.3 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AsyncAdapter (Singleton)                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │          Background Event Loop Thread                   │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  asyncio.new_event_loop()                        │  │  │
│  │  │  loop.run_forever()  (daemon thread)             │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           │ asyncio.run_coroutine_threadsafe  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Adapter Wrappers                           │  │
│  │  _DockerAdapter  │ _KubernetesAdapter │ _QEMUAdapter   │  │
│  │  _PodmanAdapter  │ _VMwareAdapter    │ _VirtualBoxAdapter│ │
│  │                                                         │  │
│  │  Each wrapper:                                          │  │
│  │  - Holds reference to async backend instance            │  │
│  │  - Provides sync methods that call _run_async(coro)     │  │
│  │  - Converts typed objects → dicts for GUI consumption   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 Core Mechanism

```python
class AsyncAdapter:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # Thread-safe singleton
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def _start_loop(self):
        """Start the background event loop in a daemon thread."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run_async(self, coro, timeout: float = 30):
        """Run a coroutine in the background loop and block for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)
```

### 3.5 Lazy Backend Initialization

Backends are initialized lazily via property accessors:

```python
@property
def docker(self):
    if self._docker is None:
        from vm_harness.container.docker.backend import DockerBackend
        self._docker = DockerBackend()
        self._run_async(self._docker.connect())  # Async connect → sync wait
    return _DockerAdapter(self._docker, self._run_async)
```

### 3.6 Adapter Wrapper Pattern

Each adapter wraps an async backend and converts typed return values to GUI-friendly dicts:

```python
class _DockerAdapter:
    def __init__(self, backend, run_async):
        self._backend = backend
        self._run = run_async

    def list_containers(self, all: bool = True) -> list:
        containers = self._run(self._backend.list_containers(all=all))
        # Convert Container objects to dicts for GUI consumption
        result = []
        for c in containers:
            if hasattr(c, 'name'):
                result.append({
                    "name": c.name,
                    "image": str(c.image) if hasattr(c, 'image') else "",
                    "status": c.status if hasattr(c, 'status') else "",
                    "ports": str(c.ports) if hasattr(c, 'ports') else "",
                })
            elif isinstance(c, dict):
                result.append(c)
        return result
```

### 3.7 Available Adapters

| Adapter | Backend Class | Module |
|---------|--------------|--------|
| `adapter.docker` | `DockerBackend` | `vm_harness.container.docker.backend` |
| `adapter.kubernetes` | `KubernetesBackend` | `vm_harness.container.kubernetes.backend` |
| `adapter.podman` | `PodmanBackend` | `vm_harness.container.podman.backend` |
| `adapter.qemu` | `QEMUBackend` | `vm_harness.hypervisor.qemu.backend` |
| `adapter.vmware` | `VMwareBackend` | `vm_harness.hypervisor.vmware.backend` |
| `adapter.vbox` | `VirtualBoxBackend` | `vm_harness.hypervisor.virtualbox.backend` |

---

## 4. Backend Abstraction Layer

### 4.1 HypervisorBackend (ABC)

`src/vm_harness/hypervisor/backend.py` defines the abstract base class for all hypervisor backends.

#### Key Data Classes

| Class | Purpose |
|-------|---------|
| `VMConfig` | Configuration for creating a new VM (name, RAM, CPUs, disk, network, display, boot, etc.) |
| `VMStatus` | Snapshot of a VM's current state (state, PID, uptime, IP, metrics, etc.) |
| `VMMetrics` | Real-time VM metrics (CPU, RAM, disk I/O, network I/O) |
| `VMDisplay` | Display connection details (type, host, port, password, URI) |
| `VMNetwork` | Network interface configuration (name, mode, MAC, IP) |
| `VMSnapshot` | Snapshot metadata (name, description, created_at, parent/children) |
| `VMConsole` | Console/terminal access details |
| `VMGuestInfo` | Guest OS information (hostname, OS, IPs, uptime, filesystems) |

#### Enums

- `VMState`: STOPPED, RUNNING, PAUSED, SUSPENDED, ERROR, STARTING, STOPPING, SAVING, RESTORING, UNKNOWN
- `DisplayType`: SPICE, VNC, SDL, GTK, HEADLESS, RDP, CONSOLE
- `NetworkMode`: NAT, BRIDGED, HOST_ONLY, INTERNAL, NONE
- `SnapshotMode`: INTERNAL, EXTERNAL

#### Exception Hierarchy

```
HypervisorError (base)
├── VMNotFoundError
├── VMAlreadyRunningError
├── VMNotRunningError
├── BackendNotAvailableError
├── OperationNotSupportedError
└── VMMigrationError
```

#### ABC Method Categories

| Category | Methods |
|----------|---------|
| **Lifecycle** | `create_vm`, `destroy_vm`, `start_vm`, `stop_vm`, `pause_vm`, `resume_vm`, `reset_vm`, `reboot_vm`, `shutdown_guest` |
| **Discovery** | `list_vms`, `find_vm` |
| **Status** | `get_status`, `get_config`, `update_config` |
| **Metrics** | `get_metrics`, `stream_metrics` |
| **Display** | `get_display`, `set_display_password`, `screenshot` |
| **Console** | `get_console`, `send_console_data`, `receive_console_data` |
| **Guest Agent** | `guest_exec`, `guest_info`, `guest_file_read`, `guest_file_write` |
| **Snapshots** | `list_snapshots`, `create_snapshot`, `restore_snapshot`, `delete_snapshot` |
| **Disk** | `resize_disk`, `add_disk`, `eject_cdrom`, `insert_cdrom` |
| **Networking** | `list_network_interfaces`, `add_network_interface`, `remove_network_interface`, `connect_network` |
| **Migration** | `migrate_vm` |
| **Import/Export** | `export_vm`, `import_vm` |
| **Cloning** | `clone_vm` |
| **Resource Limits** | `set_resource_limits` |
| **USB** | `attach_usb`, `detach_usb` |
| **Events** | `on_vm_started`, `on_vm_stopped`, `on_vm_error` |

### 4.2 ContainerBackend (ABC)

`src/vm_harness/container/backend.py` defines the abstract base for container runtimes.

#### Key Data Classes

| Class | Purpose |
|-------|---------|
| `Container` | Running/stopped container (id, name, status, image, ports, labels) |
| `ContainerConfig` | Configuration for creating a container |
| `ContainerStats` | Real-time resource usage (CPU, memory, network, I/O) |
| `CommandResult` | Result of exec_command (stdout, stderr, returncode) |
| `ContainerImage` | Container image (id, tags, size) |
| `ContainerNetwork` | Container network (name, driver, scope) |
| `ContainerVolume` | Container volume (name, driver, mountpoint) |

#### ABC Method Categories

| Category | Methods |
|----------|---------|
| **Lifecycle** | `list_containers`, `get_container`, `create_container`, `start_container`, `stop_container`, `restart_container`, `remove_container` |
| **Execution** | `exec_command`, `get_logs` |
| **Statistics** | `get_stats` |
| **Images** | `list_images`, `pull_image`, `remove_image` |
| **Networks** | `list_networks`, `create_network` |
| **Volumes** | `list_volumes`, `create_volume` |

### 4.3 HypervisorRegistry

`src/vm_harness/hypervisor/registry.py` auto-detects and selects the best available backend.

```
┌─────────────────────────────────────────────────────────┐
│                 HypervisorRegistry                       │
│                                                         │
│  auto_detect() ──▶ probes each registered backend      │
│                     in priority order:                   │
│                     1. QEMU                             │
│                     2. VMware                           │
│                     3. VirtualBox                       │
│                     4. WSL (Windows only)               │
│                     5. Hyper-V (Windows only)           │
│                     6. KVM (Linux only)                 │
│                                                         │
│  get_best_backend() ──▶ returns highest-priority        │
│                          available backend instance      │
│                                                         │
│  set_preferred(name) ──▶ override auto-selection        │
│                                                         │
│  register(name, class) ──▶ add custom backend           │
└─────────────────────────────────────────────────────────┘
```

### 4.4 Backend Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  Backend Abstraction Layer                       │
│                                                                 │
│  ┌──────────────────────┐    ┌──────────────────────────────┐   │
│  │  ContainerBackend    │    │    HypervisorBackend (ABC)     │   │
│  │  (ABC)               │    │                              │   │
│  │                      │    │  VMConfig / VMStatus        │   │
│  │  Container           │    │  VMMetrics / VMDisplay      │   │
│  │  ContainerConfig     │    │  VMNetwork / VMSnapshot     │   │
│  │  ContainerStats      │    │  VMConsole / VMGuestInfo    │   │
│  │  CommandResult       │    │                              │   │
│  │  ContainerImage      │    │  initialize() / shutdown()  │   │
│  │  ContainerNetwork    │    │  list_vms() / create_vm()   │   │
│  │  ContainerVolume     │    │  start_vm() / stop_vm()     │   │
│  └──────────┬───────────┘    └──────────────┬───────────────┘   │
│             │                               │                   │
│     ┌───────┼───────────┐          ┌────────┼────────────┐      │
│     │       │           │          │        │            │      │
│     ▼       ▼           ▼          ▼        ▼            ▼      │
│  ┌──────┐┌──────┐┌────────┐  ┌──────┐┌──────┐┌──────────┐     │
│  │Docker││K8s   ││Podman  │  │ QEMU ││VMware││VirtualBox│     │
│  │Backend││Backend││Backend │  │Backend││Backend││ Backend  │     │
│  └──────┘└──────┘└────────┘  └──────┘└──────┘└──────────┘     │
│                              ┌──────┐┌──────┐                  │
│                              │ WSL  ││HyperV│                  │
│                              │Backend││Backend│                  │
│                              └──────┘└──────┘                  │
│                                                                 │
│              HypervisorRegistry (auto-detect & select)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Streaming Bridge Protocol

### 5.1 Overview

The streaming bridge (`streaming_bridge.py`) provides remote desktop streaming and input injection. It captures desktop frames, encodes them as JPEG, and streams them to connected clients over WebSocket. Client input events (mouse, keyboard) are injected back into the host desktop.

### 5.2 WebSocket Endpoints (Port 8445)

| Endpoint | Protocol | Purpose |
|----------|----------|---------|
| `/ws/stream` | WebSocket | Main streaming channel — frame broadcast + input events |
| `/terminal/{container}` | WebSocket | Docker container terminal access |
| `/health` | HTTP GET | Health check |
| `/monitors` | HTTP GET | List available monitors |
| `/config` | HTTP POST | Update bridge configuration |

### 5.3 Frame Capture Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                   Frame Capture Pipeline                      │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Capture    │    │   Encode     │    │   Broadcast  │   │
│  │              │    │              │    │              │   │
│  │ Windows GDI  │───▶│ PIL / JPEG   │───▶│ WebSocket    │   │
│  │ StretchBlt   │    │ quality=85   │    │ binary send  │   │
│  │ or PIL       │    │ optimize=True │    │              │   │
│  │ ImageGrab    │    │              │    │              │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                              │
│  Configurable:                                               │
│  - FPS: 1-120 (default 60)                                  │
│  - Quality: 10-100 (default 85)                             │
│  - Max resolution: 1920x1080                                │
│                                                              │
│  Runs in background thread, stores last frame in memory     │
└──────────────────────────────────────────────────────────────┘
```

### 5.4 Input Injection

```
┌──────────────────────────────────────────────────────────────┐
│                    Input Injection                            │
│                                                              │
│  Client WebSocket message:                                    │
│  {                                                           │
│    "type": "input",                                         │
│    "input_type": "mouse_move" | "mouse_click" |             │
│                   "scroll" | "key",                         │
│    "x": 500, "y": 300,                                      │
│    "button": "left", "pressed": true,                        │
│    "key_code": 65                                            │
│  }                                                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                InputInjector                         │     │
│  │                                                      │     │
│  │  Primary: enigo (cross-platform)                     │     │
│  │  Fallback: ctypes.windll.user32 (Windows)            │     │
│  │                                                      │     │
│  │  Methods:                                            │     │
│  │  - mouse_move(x, y)                                  │     │
│  │  - mouse_relative(dx, dy)                            │     │
│  │  - mouse_click(button, pressed)                      │     │
│  │  - scroll(dx, dy)                                    │     │
│  │  - key(key_code, pressed)                            │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### 5.5 QMP Bridge (GUI ↔ QMP)

The QMP bridge (`gui/qmp_bridge.py`) is a separate component that bridges the async QMP (QEMU Machine Protocol) client to PyQt5 signals.

```
┌──────────────────────────────────────────────────────────────┐
│                     QMPBridge                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Background Thread (threading.Thread, NOT QThread)     │  │
│  │  - asyncio.new_event_loop()                            │  │
│  │  - loop.run_forever()                                  │  │
│  │  - QMPClient connects to QEMU QMP socket              │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           │ asyncio.run_coroutine_threadsafe  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PyQt5 Signals (emitted from bg thread → main thread)  │  │
│  │                                                         │  │
│  │  connected(bool)     — QMP connection state            │  │
│  │  vm_status(dict)     — VM status update                │  │
│  │  error(str)          — Error message                   │  │
│  │  command_result(dict) — QMP command result             │  │
│  │  active_vm_changed(str) — Active VM changed            │  │
│  │  reconnecting(int, float) — Reconnect attempt + delay  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Reconnection: exponential backoff                           │
│  0.5s → 1s → 2s → 4s → 8s → 16s (max)                     │
│  Max 10 attempts before giving up                             │
└──────────────────────────────────────────────────────────────┘
```

### 5.6 Streaming Bridge Protocol Message Types

| Direction | Message Type | Payload |
|-----------|-------------|---------|
| Client → Server | `config` | `{quality, fps, width, height, monitor_id, input_enabled}` |
| Client → Server | `input` | `{input_type, x, y, button, pressed, dx, dy, key_code}` |
| Client → Server | `ping` | `{time}` |
| Client → Server | `stats_request` | `{}` |
| Server → Client | `config_ack` | `{quality, fps, width, height}` |
| Server → Client | `pong` | `{time}` |
| Server → Client | `stats` | `{bytes_sent, frames_sent, clients}` |
| Server → Client | binary frame | JPEG image bytes |

---

## 6. REST API Surface

### 6.1 Server Configuration

- **Port:** 8443
- **Framework:** aiohttp
- **TLS:** Self-signed certificate (auto-generated if missing)
- **Binding:** 0.0.0.0 (all interfaces, protected by auth)

### 6.2 Middleware Pipeline

```
Request → json_error_middleware → api_auth_middleware → Route Handler
                                    │
                                    ▼
                              Tailscale check
                              or API key validation
                              (X-API-Key header)
```

### 6.3 Authentication

| Mechanism | Details |
|-----------|---------|
| **API Key** | `X-API-Key` header or `Authorization: Bearer <key>` |
| **Public paths** | `/health`, `/api/v1/auth/pair`, `/api/v1/auth/public-key` |
| **Pairing** | QR code or manual token entry, 24h TTL |
| **RBAC** | Role-based access control via `RBACEnforcer` |
| **Rate limiting** | Per-key request throttling |

### 6.4 Complete Endpoint Reference

#### Health & Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/api/v1/` | Dashboard summary (VMs, metrics, tailscale IP) |

#### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/pair` | Pair a mobile client |
| GET | `/api/v1/auth/verify` | Verify pairing status |
| POST | `/api/v1/auth/revoke` | Revoke a pairing |
| GET | `/api/v1/auth/public-key` | Get Ed25519 public key |

#### VM Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/vms` | List all VMs |
| POST | `/api/v1/vms` | Create a new VM |
| GET | `/api/v1/vms/{name}` | Get VM details |
| POST | `/api/v1/vms/{name}/{action}` | VM action (start/stop/reset/pause/resume/powerdown/eject) |
| GET | `/api/v1/vms/{name}/snapshots` | List VM snapshots |
| POST | `/api/v1/vms/{name}/snapshots` | Create snapshot |
| POST | `/api/v1/vms/{name}/snapshots/{snapshot_name}/restore` | Restore snapshot |
| POST | `/api/v1/vms/{name}/qmp` | Send QMP command |

#### Container Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/containers` | List all containers |
| POST | `/api/v1/containers` | Create a container |
| GET | `/api/v1/containers/{id}` | Inspect a container |
| POST | `/api/v1/containers/{id}/start` | Start a container |
| POST | `/api/v1/containers/{id}/stop` | Stop a container |
| POST | `/api/v1/containers/{id}/restart` | Restart a container |
| DELETE | `/api/v1/containers/{id}` | Remove a container |
| POST | `/api/v1/containers/{id}/exec` | Execute command in container |
| GET | `/api/v1/containers/{id}/logs` | Get container logs |
| GET | `/api/v1/containers/{id}/stats` | Get container stats |
| GET | `/api/v1/containers/stats` | Get all container stats (headless server) |

#### Kubernetes Operations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/kubernetes/clusters` | List clusters |
| POST | `/api/v1/kubernetes/clusters` | Create a cluster |
| GET | `/api/v1/kubernetes/clusters/{name}` | Get cluster details |
| DELETE | `/api/v1/kubernetes/clusters/{name}` | Delete a cluster |
| GET | `/api/v1/kubernetes/namespaces` | List namespaces |
| POST | `/api/v1/kubernetes/namespaces` | Create a namespace |
| GET | `/api/v1/kubernetes/pods` | List pods |
| GET | `/api/v1/kubernetes/pods/{name}` | Get pod details |
| DELETE | `/api/v1/kubernetes/pods/{name}` | Delete a pod |
| GET | `/api/v1/kubernetes/pods/{name}/logs` | Get pod logs |
| GET | `/api/v1/kubernetes/deployments` | List deployments |
| POST | `/api/v1/kubernetes/deployments` | Create a deployment |
| POST | `/api/v1/kubernetes/deployments/{name}/scale` | Scale a deployment |
| GET | `/api/v1/kubernetes/services` | List services |
| POST | `/api/v1/kubernetes/services` | Create a service |
| GET | `/api/v1/kubernetes/nodes` | List nodes |
| POST | `/api/v1/kubernetes/nodes/{name}/cordon` | Cordon a node |
| POST | `/api/v1/kubernetes/nodes/{name}/uncordon` | Uncordon a node |

#### Federation & Service Mesh

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/federation/status` | Federation health |
| GET | `/api/v1/federation/members` | List member clusters |
| POST | `/api/v1/federation/members` | Join a cluster |
| DELETE | `/api/v1/federation/members/{name}` | Remove a member |
| GET | `/api/v1/federation/mesh/services` | Discover services |
| POST | `/api/v1/federation/mesh/expose` | Expose a service |
| DELETE | `/api/v1/federation/mesh/expose/{name}` | Unexpose a service |
| GET | `/api/v1/federation/dns` | List DNS records |
| POST | `/api/v1/federation/dns` | Add DNS record |
| GET | `/api/v1/federation/tailscale` | Tailscale status |
| POST | `/api/v1/federation/tailscale/exit-node` | Configure exit node |

#### Streaming & Real-time

| Method | Path | Description |
|--------|------|-------------|
| WS | `/api/v1/vms/{name}/console` | WebSocket QMP console |
| WS | `/api/v1/vms/{name}/terminal` | WebSocket SSH terminal |
| WS | `/api/v1/containers/{id}/exec-ws` | WebSocket container exec |
| GET | `/api/v1/logs/stream` | SSE log tailing |
| GET | `/api/v1/metrics/stream` | SSE metrics streaming |
| GET | `/api/v1/events/stream` | SSE system events |
| GET | `/api/v1/kubernetes/pods/{name}/logs/stream` | SSE pod logs |

#### Other

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/metrics` | Get VM metrics |
| GET | `/api/v1/settings` | Get settings |
| PUT | `/api/v1/settings` | Update settings |
| GET | `/api/v1/credentials` | List credentials |
| GET | `/api/v1/credentials/{name}` | Get credential details |
| GET | `/api/v1/security/audit` | Get audit log |
| GET | `/api/v1/logs` | Get application logs |

### 6.5 API Response Format

All responses use JSON:

```json
// Success
{"data": "...", "status": "ok"}

// Error
{"error": "error_code", "detail": "Human-readable description"}
```

---

## 7. Single-Instance Lock Mechanism

### 7.1 Overview

The GUI application enforces single-instance execution using a PID-based lock file at `gui/.vmharness_gui.lock`.

### 7.2 Mechanism

```
┌──────────────────────────────────────────────────────────────┐
│                Single-Instance Lock Flow                      │
│                                                              │
│  1. Check if .vmharness_gui.lock exists                     │
│     │                                                        │
│     ├── No ──▶ Write current PID to lock file ──▶ Continue  │
│     │                                                        │
│     └── Yes ──▶ Read PID from lock file                     │
│                  │                                           │
│                  ├── PID is running ──▶ Exit (log & return)  │
│                  │                                           │
│                  └── PID is dead ──▶ Delete stale lock       │
│                                       ──▶ Write new PID      │
│                                           ──▶ Continue       │
│                                                              │
│  2. Register atexit handler to release lock on exit         │
│                                                              │
│  3. Lock is automatically released if process crashes        │
│     (OS cleans up file handles; stale PID detection         │
│      handles the rest on next launch)                        │
└──────────────────────────────────────────────────────────────┘
```

### 7.3 Implementation Details

```python
_LOCK_FILE = script_dir / ".vmharness_gui.lock"

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
        # Stale lock — remove it
        try:
            _LOCK_FILE.unlink()
        except OSError:
            pass

    _LOCK_FILE.write_text(str(os.getpid()))
    return True
```

### 7.4 PID Liveness Check (Windows)

Uses Windows API to check if a process is alive:

```python
def _is_pid_running(pid: int) -> bool:
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
```

### 7.5 Lock Release

```python
def _release_lock():
    """Release the single-instance lock on clean exit."""
    try:
        if _LOCK_FILE.exists():
            pid = int(_LOCK_FILE.read_text().strip())
            if pid == os.getpid():
                _LOCK_FILE.unlink()
    except (ValueError, OSError):
        pass
```

Registered via `atexit.register(_release_lock)`.

---

## 8. Resilience System

### 8.1 Overview

`gui/resilience.py` implements a comprehensive self-healing system with six components orchestrated by `SelfHealingOrchestrator`.

```
┌──────────────────────────────────────────────────────────────────┐
│                SelfHealingOrchestrator                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ CrashHandler │  │ AtomicState  │  │   ProcessGuardian    │   │
│  │              │  │ (WAL)        │  │                      │   │
│  │ sys.except-  │  │ Write-ahead  │  │ Monitors main proc   │   │
│  │ hook +       │  │ logging for  │  │ Auto-restarts on     │   │
│  │ signal       │  │ crash recovery│  │ crash (max 3)        │   │
│  │ handlers     │  │              │  │                      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│         ▼                 ▼                      ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ HotReloader  │  │ Failover     │  │   HealthChecker      │   │
│  │              │  │ Manager      │  │                      │   │
│  │ Watches src  │  │              │  │ Periodic health      │   │
│  │ files for    │  │ Live backup  │  │ verification with    │   │
│  │ changes      │  │ process for  │  │ auto-recovery        │   │
│  │ (dev mode)   │  │ zero-downtime│  │ (max 3 failures)     │   │
│  │              │  │ failover     │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 CrashHandler

**Purpose:** Catches all unhandled exceptions, saves structured crash reports, and attempts recovery.

**Key features:**
- Installs `sys.excepthook` to intercept unhandled exceptions
- Installs signal handlers for SIGINT and SIGTERM (graceful shutdown)
- Saves crash reports as JSON to `logs/crash_*.json`
- Tracks crash count within a 60-second window
- Exits cleanly after 5 crashes in 60 seconds (prevents crash loops)
- Runs registered recovery callbacks

```python
@dataclass
class CrashReport:
    timestamp: str
    exception_type: str
    exception_message: str
    traceback: str
    pid: int
    thread: str
    memory_mb: float
    state_file: str = ""
```

### 8.3 AtomicState (Write-Ahead Logging)

**Purpose:** Crash-safe state persistence using write-ahead logging (WAL).

**Mechanism:**
1. State changes are first appended to `vm_state.wal` (with `fsync`)
2. In-memory state is updated
3. Full state is committed to `vm_state.json` via atomic temp-file + rename
4. WAL is cleared after successful commit
5. On startup, WAL is replayed if it exists (recovers uncommitted changes)

**Integrity verification:**
- Each state has a SHA-256 checksum
- `verify_integrity()` detects corrupted states
- `recover()` reloads from WAL if corruption detected

```
┌──────────────────────────────────────────────────────────┐
│                  AtomicState WAL Flow                      │
│                                                          │
│  save(vm_state):                                         │
│    1. Compute checksum                                   │
│    2. Append to WAL (fsync)  ←── crash-safe point        │
│    3. Update in-memory state                             │
│    4. Commit to main file (temp + rename)                │
│    5. Clear WAL                                          │
│                                                          │
│  _load():                                                │
│    1. Read main state file                               │
│    2. If WAL exists, replay entries                     │
│    3. Clear WAL after replay                             │
│                                                          │
│  verify_integrity():                                     │
│    - Recompute checksums, compare with stored            │
│    - Return list of corrupted state names                │
│                                                          │
│  recover():                                              │
│    - Detect corrupted states                             │
│    - Remove them                                         │
│    - Reload from WAL                                     │
│    - Re-commit                                           │
└──────────────────────────────────────────────────────────┘
```

### 8.4 ProcessGuardian

**Purpose:** Monitors the main process and auto-restarts on crash.

**Configuration:**
- Check interval: 5 seconds
- Max restarts: 3
- Restart window: 5 minutes (resets counter after window)

**Flow:**
1. Starts a daemon thread running `_guard_loop()`
2. Periodically calls the health callback
3. On failure, calls the restart callback (which uses `os.execv` to restart)
4. Gives up after max restarts within the window

### 8.5 HotReloader

**Purpose:** Watches source files for changes during development.

**Configuration:**
- Watch paths: `gui/`, `src/`
- Debounce: 1.0 second
- Only active when `VM_HARNESS_DEV` env var is set

**Flow:**
1. Scans all `.py` files in watch paths, computing MD5 hashes
2. Polls every 1 second for changes
3. On change, calls the reload callback with list of changed files
4. Debounce prevents rapid-fire reloads

### 8.6 FailoverManager

**Purpose:** Manages a live backup process for zero-downtime failover.

**Mechanism:**
- Tracks primary and backup PIDs
- `trigger_failover()` promotes backup to primary
- `is_healthy()` checks if primary PID is alive via `psutil`
- Thread-safe with `threading.Lock`

### 8.7 HealthChecker

**Purpose:** Periodic health verification with auto-recovery.

**Configuration:**
- Check interval: 10 seconds
- Max consecutive failures: 3

**Flow:**
1. Runs registered health check callbacks
2. If all pass, resets failure counter
3. If any fail, increments counter
4. After max failures, runs all registered recovery actions
5. Resets counter after recovery

### 8.8 SelfHealingOrchestrator

Wires all components together:

```python
class SelfHealingOrchestrator:
    def __init__(self):
        self.crash_handler = CrashHandler()
        self.atomic_state = AtomicState()
        self.guardian = ProcessGuardian()
        self.hot_reloader = HotReloader()
        self.failover = FailoverManager()
        self.health = HealthChecker()
        self._wire_components()

    def _wire_components(self):
        # Crash handler recovery → atomic state recovery
        self.crash_handler.register_recovery(self._on_crash_recovery)
        # Guardian health check → health checker
        self.guardian.set_health_callback(self._health_check)
        self.guardian.set_restart_callback(self._restart)
        # Health checker → atomic state recovery
        self.health.add_recovery(self._on_health_recovery)
```

### 8.9 Resilience State Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                  Resilience State Machine                     │
│                                                              │
│    ┌─────────┐                                               │
│    │ Normal  │◀──────────────────────────────────────┐       │
│    └────┬────┘                                       │       │
│         │                                            │       │
│    Crash detected                                Recovery     │
│         │                                      successful    │
│         ▼                                            │       │
│    ┌─────────┐     ┌──────────┐     ┌──────────┐    │       │
│    │ Crash   │────▶│ Atomic   │────▶│ Health   │────┘       │
│    │ Handler │     │ State    │     │ Checker  │            │
│    └─────────┘     │ Recover  │     │ Recover  │            │
│                    └──────────┘     └──────────┘            │
│                                                              │
│    ┌─────────┐                                               │
│    │ Process │────▶ os.execv() ──▶ Restart process          │
│    │Guardian │                                               │
│    └─────────┘                                               │
│                                                              │
│    ┌─────────┐                                               │
│    │ Failover│────▶ Promote backup ──▶ Continue as primary   │
│    │ Manager │                                               │
│    └─────────┘                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. TLS/SSL Setup

### 9.1 Certificate Generation

`scripts/generate_cert.py` creates a self-signed RSA certificate:

```python
def generate_self_signed_cert(
    cert_path: Path = CERT_FILE,    # cert.pem
    key_path: Path = KEY_FILE,      # key.pem
    valid_days: int = 365,
    common_name: str = "localhost",
) -> tuple[Path, Path]:
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    # ... build X.509 cert with SAN for localhost + 127.0.0.1
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.Random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=valid_days))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name),
                x509.IPAddress(ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
```

**Certificate properties:**
- Key: 2048-bit RSA
- Signature: SHA-256
- Validity: 365 days
- SAN: `localhost`, `127.0.0.1`
- Key file permissions: `0o600` (owner read/write only)

### 9.2 SSL Context Creation

`headless_server.py` creates the SSL context:

```python
def create_ssl_context(cert_path: Path = CERT_FILE, key_path: Path = KEY_FILE) -> ssl.SSLContext:
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return ssl_ctx
```

### 9.3 TLS Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    TLS Setup Flow                             │
│                                                              │
│  1. Check if cert.pem and key.pem exist                     │
│     │                                                        │
│     ├── Yes ──▶ Use existing certificates                   │
│     │                                                        │
│     └── No ──▶ Run scripts/generate_cert.py                 │
│                 │                                            │
│                 ├── Success ──▶ Certificates created         │
│                 │                                            │
│                 └── Failure ──▶ Fall back to plain HTTP      │
│                                                              │
│  2. Create SSLContext                                       │
│                                                              │
│  3. Start aiohttp server with SSLContext                    │
│     │                                                        │
│     ├── TLS enabled ──▶ https://0.0.0.0:8443               │
│     │                                                        │
│     └── TLS disabled (--no-tls) ──▶ http://0.0.0.0:8443     │
│                                                              │
│  Note: When using Tailscale, TLS is optional because        │
│  Tailscale already provides WireGuard encryption.           │
│  The API server binds to the Tailscale IP with source-IP    │
│  filtering on 100.0.0.0/8.                                  │
└──────────────────────────────────────────────────────────────┘
```

### 9.4 Tailscale Integration

When Tailscale is available, the API server can bind to the Tailscale interface IP (100.x.y.z) with source-IP filtering on `100.0.0.0/8`. This provides:
- WireGuard encryption (no additional TLS needed)
- No LAN or localhost exposure
- MagicDNS name resolution

---

## 10. Plugin API Design (Proposed)

### 10.1 Design Goals

- Allow third-party extensions without modifying core code
- Support both GUI panels and backend plugins
- Maintain type safety through the existing ABC patterns
- Enable hot-pluggable functionality

### 10.2 Proposed Plugin Interface

```python
# vm_harness/plugins/base.py (proposed)

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PluginMetadata:
    """Plugin descriptor."""
    name: str
    version: str
    description: str
    author: str
    category: str  # "panel", "backend", "middleware", "bridge"
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)


class VMHarnessPlugin(ABC):
    """Base class for all VM-Harness plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        ...

    @abstractmethod
    async def initialize(self, context: "PluginContext") -> None:
        """Initialize the plugin with the given context."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up plugin resources."""
        ...


class PanelPlugin(VMHarnessPlugin):
    """Plugin that provides a GUI panel."""

    @abstractmethod
    def create_panel(self, parent) -> "QWidget":
        """Create and return the panel widget."""
        ...


class BackendPlugin(VMHarnessPlugin):
    """Plugin that provides a new backend implementation."""

    @abstractmethod
    def create_backend(self) -> "HypervisorBackend | ContainerBackend":
        """Create and return a backend instance."""
        ...


class MiddlewarePlugin(VMHarnessPlugin):
    """Plugin that provides API middleware."""

    @abstractmethod
    def create_middleware(self):
        """Create and return an aiohttp middleware."""
        ...


@dataclass
class PluginContext:
    """Context passed to plugins during initialize()."""
    settings: Dict[str, Any]
    event_loop: Any  # asyncio.AbstractEventLoop
    bridge_registry: Any  # Access to QMP/SSH bridges
    api_app: Any  # aiohttp Application (for middleware plugins)
```

### 10.3 Plugin Discovery

```python
# vm_harness/plugins/manager.py (proposed)

class PluginManager:
    """Discovers, loads, and manages plugins."""

    PLUGIN_ENTRY_POINT = "vmharness.plugins"

    def __init__(self, plugin_dirs: List[Path] | None = None):
        self._plugins: Dict[str, VMHarnessPlugin] = {}
        self._plugin_dirs = plugin_dirs or [
            Path.home() / ".vmharness" / "plugins",
            Path(__file__).resolve().parent.parent / "plugins",
        ]

    def discover_plugins(self) -> List[PluginMetadata]:
        """Scan plugin directories and entry points for plugins."""
        # 1. Scan plugin directories for Python files
        # 2. Check package entry points (setuptools)
        # 3. Load and validate plugin classes
        ...

    def load_plugin(self, name: str) -> VMHarnessPlugin:
        """Load and initialize a plugin by name."""
        ...

    def unload_plugin(self, name: str) -> None:
        """Unload and clean up a plugin."""
        ...

    def get_panels(self) -> List[PanelPlugin]:
        """Get all loaded panel plugins."""
        ...

    def get_backends(self) -> List[BackendPlugin]:
        """Get all loaded backend plugins."""
        ...
```

### 10.4 Plugin Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    Plugin System (Proposed)                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   PluginManager                             │  │
│  │                                                            │  │
│  │  discover_plugins() ──▶ scan dirs + entry points          │  │
│  │  load_plugin(name)   ──▶ import + initialize               │  │
│  │  unload_plugin(name) ──▶ shutdown + cleanup                │  │
│  └────────────────────────────┬───────────────────────────────┘  │
│                               │                                  │
│              ┌────────────────┼────────────────┐                 │
│              │                │                │                 │
│              ▼                ▼                ▼                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │ PanelPlugin   │  │ BackendPlugin │  │MiddlewarePlugin│      │
│  │               │  │               │  │               │       │
│  │ create_panel()│  │create_backend()│  │create_middleware()│  │
│  │ → QWidget     │  │ → Hypervisor  │  │ → aiohttp     │       │
│  │               │  │   Backend     │  │   middleware  │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                  │
│  Plugin directories:                                             │
│  - ~/.vmharness/plugins/                                        │
│  - <project>/plugins/                                           │
│  - Package entry points (vmharness.plugins)                     │
│                                                                  │
│  Plugin context provides:                                        │
│  - Settings access                                              │
│  - Event loop access                                            │
│  - Bridge registry (QMP/SSH)                                    │
│  - API app reference (for middleware)                           │
└──────────────────────────────────────────────────────────────────┘
```

### 10.5 Example Plugin

```python
# Example: A simple monitoring panel plugin

from vm_harness.plugins.base import (
    PluginMetadata, PanelPlugin, PluginContext
)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


class SystemMonitorPlugin(PanelPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="system-monitor",
            version="1.0.0",
            description="System resource monitor panel",
            author="Your Name",
            category="panel",
        )

    async def initialize(self, context: PluginContext) -> None:
        self._context = context
        self._settings = context.settings

    async def shutdown(self) -> None:
        pass

    def create_panel(self, parent) -> QWidget:
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("System Monitor"))
        # ... add monitoring widgets
        return panel
```

---

## 11. Directory Structure

```
QEMU-MCP/
├── gui/                          # PyQt5 GUI application
│   ├── __main__.py               # GUI entry point (single-instance, resilience)
│   ├── main_window.py            # MainWindow, Sidebar, TitleBar
│   ├── panels.py                 # DashboardPanel
│   ├── panels_*.py               # All other panel implementations
│   ├── async_adapter.py          # AsyncAdapter singleton
│   ├── qmp_bridge.py             # QMP bridge (async → PyQt5 signals)
│   ├── ssh_bridge.py             # SSH bridge
│   ├── multi_vm.py               # MultiVMManager
│   ├── multi_vm_qmp_bridge.py    # Multi-VM QMP bridge
│   ├── resilience.py             # CrashHandler, AtomicState, etc.
│   ├── atomic_state.py           # Atomic state management
│   ├── hot_reloader.py           # Development hot reload
│   ├── process_guardian.py       # Process monitoring
│   ├── theme.py                  # Theme constants
│   ├── widgets.py                # Reusable UI widgets
│   ├── credential_store.py       # Credential management
│   ├── audit_log.py              # Audit logging
│   ├── chat_engine.py            # AI chat engine
│   ├── api_providers.py          # AI provider management
│   ├── api_server.py             # In-process API server (pairing)
│   ├── provider_store.py         # Provider configuration
│   ├── iso_manager.py            # ISO download management
│   ├── iso_downloader.py         # ISO download logic
│   ├── metrics_store.py          # Metrics storage
│   ├── snapshot_scheduler.py     # Scheduled snapshots
│   ├── vm_cloner.py              # VM cloning
│   ├── test_executor.py          # Test execution
│   ├── test_tool_executor.py     # Test tool execution
│   ├── dialogs_container_logs.py # Container logs dialog
│   └── vmware_vbox_panel.py      # VMware/VirtualBox panel
│
├── src/
│   ├── vm_harness/               # Core library
│   │   ├── __init__.py
│   │   ├── api/                  # REST API
│   │   │   ├── middleware/       # Auth, rate limiting, RBAC
│   │   │   ├── routes/           # Route handlers
│   │   │   │   ├── containers.py
│   │   │   │   ├── federation.py
│   │   │   │   ├── kubernetes.py
│   │   │   │   ├── stacks.py
│   │   │   │   ├── streaming.py
│   │   │   │   └── templates.py
│   │   │   └── schemas/          # Request/response schemas
│   │   ├── container/            # Container backends
│   │   │   ├── backend.py        # ContainerBackend ABC
│   │   │   ├── docker/           # Docker backend
│   │   │   ├── kubernetes/       # Kubernetes backend
│   │   │   └── podman/           # Podman backend
│   │   ├── hypervisor/           # Hypervisor backends
│   │   │   ├── backend.py        # HypervisorBackend ABC + VMConfig
│   │   │   ├── registry.py       # HypervisorRegistry
│   │   │   ├── qemu/             # QEMU backend
│   │   │   ├── vmware/           # VMware backend
│   │   │   ├── virtualbox/       # VirtualBox backend
│   │   │   ├── wsl/              # WSL backend
│   │   │   ├── hyperv/           # Hyper-V backend
│   │   │   └── kvm/              # KVM backend
│   │   ├── continuum/            # Continuum transport (QUIC, tunnels)
│   │   └── security/             # Security utilities
│   │       ├── audit.py
│   │       ├── credentials.py
│   │       ├── pairing.py
│   │       └── rbac.py
│   │
│   └── vm_mcp/                   # MCP server (separate component)
│       ├── __init__.py
│       ├── __main__.py
│       ├── api_server.py         # QMCMApiServer (base for HeadlessServer)
│       ├── config.py             # VmMCPSettings, Secrets
│       ├── qmp_client.py         # Async QMP client
│       ├── server.py             # MCP server
│       ├── ssh_client.py         # Async SSH client
│       ├── setup.py              # VM setup helpers
│       ├── skills/               # MCP skills
│       └── tools/                # MCP tools
│           ├── base.py
│           ├── guest_ops.py
│           └── vm_lifecycle.py
│
├── streaming_bridge.py           # WebSocket streaming bridge (port 8445)
├── headless_server.py            # Headless REST API server (port 8443)
├── scripts/                      # Build and utility scripts
│   ├── generate_cert.py          # TLS certificate generation
│   ├── build_pyinstaller.py      # PyInstaller build
│   ├── generate_icon.py          # Icon generation
│   ├── setup_env.py              # Environment setup
│   └── version_from_git.py       # Version from git tags
│
├── tests/                        # Test suite
├── docs/                         # Documentation
│   └── ARCHITECTURE.md           # This file
│
├── ci/                           # CI/CD pipeline
├── dist/                         # PyInstaller distribution
├── cert.pem                      # TLS certificate (generated)
├── key.pem                       # TLS private key (generated)
└── .vmharness_state/             # Atomic state directory
    ├── vm_state.json             # Committed state
    └── vm_state.wal              # Write-ahead log
```

---

## Appendix: Key Design Patterns

| Pattern | Where Used | Purpose |
|---------|-----------|---------|
| **Singleton** | `AsyncAdapter`, `CrashHandler`, `SelfHealingOrchestrator` | Ensure single instance across application |
| **ABC** | `HypervisorBackend`, `ContainerBackend` | Define backend contracts |
| **Adapter** | `_DockerAdapter`, `_QEMUAdapter`, etc. | Bridge async backends to sync GUI |
| **Bridge** | `QMPBridge`, `SSHBridge` | Decouple async I/O from GUI thread |
| **Registry** | `HypervisorRegistry` | Auto-detect and select backends |
| **Observer** | PyQt5 signals/slots | Decouple panels from data sources |
| **Write-Ahead Log** | `AtomicState` | Crash-safe state persistence |
| **Factory** | `create_qmp_bridge()`, `get_backend()` | Create instances without exposing construction |
| **Middleware** | aiohttp middleware | Cross-cutting concerns (auth, rate limiting) |
| **Context Manager** | `HypervisorBackend.__aenter__/__aexit__` | Resource cleanup |
