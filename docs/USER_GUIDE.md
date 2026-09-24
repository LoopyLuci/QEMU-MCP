# VM-Harness User Guide

**Complete QEMU Virtual Machine Control Suite**

Control QEMU virtual machines through a PyQt5 desktop GUI, CLI, REST API, or MCP server.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
   - [Prerequisites](#prerequisites)
   - [Installing from Source](#installing-from-source)
   - [Installing the Executable (EXE)](#installing-the-executable-exe)
3. [Quick Start Tutorial](#quick-start-tutorial)
4. [Panel Reference](#panel-reference)
   - [Dashboard](#dashboard)
   - [VM Switcher](#vm-switcher)
   - [VM Control](#vm-control)
   - [Guest Terminal](#guest-terminal)
   - [Guest Agent](#guest-agent)
   - [Telemetry](#telemetry)
   - [QMP System Info](#qmp-system-info)
   - [QMP Console](#qmp-console)
   - [Snapshots](#snapshots)
   - [ISO Manager](#iso-manager)
   - [Create VM (Wizard)](#create-vm-wizard)
   - [Storage](#storage)
   - [CPU/Memory](#cpumemory)
   - [Display](#display)
   - [Advanced QEMU](#advanced-qemu)
   - [USB & Devices](#usb--devices)
   - [Network](#network)
   - [Monitoring](#monitoring)
   - [Settings](#settings)
   - [Security](#security)
   - [Automation](#automation)
   - [Troubleshoot](#troubleshoot)
   - [AI Chat](#ai-chat)
   - [AI Providers](#ai-providers)
   - [Logs](#logs)
5. [Agentic AI Chat](#agentic-ai-chat)
   - [Using the Chat Interface](#using-the-chat-interface)
   - [Available Tools](#available-tools)
   - [Chat Examples](#chat-examples)
   - [API Key Configuration](#api-key-configuration)
6. [API Provider Configuration](#api-provider-configuration)
   - [OpenRouter](#openrouter)
   - [Anthropic](#anthropic)
   - [OpenAI](#openai)
   - [Google](#google)
   - [Custom Providers](#custom-providers)
7. [Multi-VM Management](#multi-vm-management)
8. [Snapshot Scheduling](#snapshot-scheduling)
9. [Network Configuration](#network-configuration)
10. [USB Passthrough](#usb-passthrough)
11. [PCI Passthrough](#pci-passthrough)
12. [TPM & Secure Boot](#tpm--secure-boot)
13. [Audit Logging & Security](#audit-logging--security)
14. [Troubleshooting](#troubleshooting)
15. [Keyboard Shortcuts](#keyboard-shortcuts)
16. [Configuration Reference](#configuration-reference)
17. [FAQ](#faq)
18. [Contributing Guide](#contributing-guide)

---

## 1. Introduction

### What is VM-Harness?

**VM-Harness** is a comprehensive desktop application for controlling QEMU virtual machines through a PyQt5 graphical interface, CLI, REST API, and MCP server. It provides complete VM lifecycle management with 25+ specialized panels, agentic AI chat integration, multi-VM support, snapshot scheduling, USB passthrough, and more.

**VM-Harness** is developed by **Omarchy VM Control** and is released under the MIT license.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    VM-Harness Application                  │
├─────────────────────────────────────────────────────────┤
│  GUI (PyQt5)  │  CLI (argparse)  │  REST API (HTTP)   │
│       ↓          ↓                    ↓                 │
│  QMP Bridge   SSH Bridge      MCP Server               │
│       ↓          ↓                    ↓                 │
│  ────────────────────────────────────────────────        │
│  QMP/SSH Bridges (async → PyQt5 signals)                │
│       ↓          ↓                                        │
│  QEMU Process  Guest OS (via SSH)                       │
└─────────────────────────────────────────────────────────┘
```

**Key Components:**

| Component | Purpose |
|-----------|---------|
| **QMP Bridge** | Async QMP communication with PyQt5 signal integration for VM control |
| **SSH Bridge** | Async SSH communication for guest command execution and file operations |
| **Chat Engine** | Agentic AI chat with tool execution (QMP + SSH + ISO tools) |
| **Multi-VM Manager** | Manages multiple VM configurations with resource limits |
| **Credential Store** | Fernet-encrypted vault for secrets (passwords, API keys, SSH keys) |
| **Snapshot Scheduler** | Automated background snapshot creation with retention policies |
| **Process Guardian** | Self-healing: monitors and restarts QEMU processes |
| **ISO Manager** | ISO file management with internal storage and external folder scanning |

### Key Features

| Feature | Description |
|---------|-------------|
| **VM Lifecycle Control** | Start, stop, reset, suspend, resume VMs via QMP commands |
| **Guest Operations** | SSH terminal, file browser, command execution, file upload/download |
| **Snapshot Management** | Create, restore, delete VM snapshots via qemu-img |
| **ISO Management** | Browse, import, download ISO files; external folder scanning |
| **Hardware Configuration** | CPU, memory, display, USB passthrough, PCI passthrough, TPM |
| **Network Management** | Virtual networks (NAT/Bridged/Isolated), port forwarding, firewall rules |
| **AI Chat Integration** | Natural language VM control via LLM APIs (OpenRouter, Anthropic, OpenAI, Google) |
| **Monitoring & Telemetry** | Real-time CPU, RAM, disk, network charts with matplotlib |
| **Audit Logging** | Encrypted credential vault (Fernet), comprehensive log viewers |
| **Automation** | Macros, scheduled tasks, event hooks |
| **Hardware Acceleration** | WHPX (Windows), HAXM (Intel), TCG (software fallback) |
| **Multi-VM Support** | Control multiple QEMU instances with per-VM resource limits |
| **Self-Healing** | Atomic state management, process guardian, automatic recovery |

### UI Overview

The application features a **frameless dark-themed window** (PyQt5 Fusion style with custom dark palette):

**Custom Title Bar:**
- Brand icon (blue circle)
- Application name "VM-Harness" (white, bold, 18px)
- Status indicator dot (green/yellow/red)
- Status text ("Connected", "Disconnected", etc.)
- Window controls: Minimize (−), Maximize/Restore (□/❐), Close (×)

**Sidebar Navigation (180px wide):**
24 icon+label buttons organized by function, each checkable to show active panel:
- 📊 Dashboard
- 🔄 VM Switcher
- 🖥️ VM Control
- 💻 Guest Terminal
- 🤖 Guest Agent
- 📈 Telemetry
- 📋 QMP System Info
- 🔧 QMP Console
- 📸 Snapshots
- 💿 ISO Manager
- ➕ Create VM
- 💾 Storage
- 🧠 CPU/Memory
- 🖥️ Display
- ⚡ Advanced QEMU
- 🔌 USB/Devices
- 🌐 Network
- 📊 Monitoring
- ⚙️ Settings
- 🔒 Security
- 🤖 Automation
- 🔍 Troubleshoot
- 💬 AI Chat
- 🤖 AI Providers

**Main Content Area:**
- QStackedWidget displaying the active panel (dark background #0f172a)
- Each panel uses Card widgets with consistent styling

**Status Bar (bottom):**
- Shows current panel name ("Panel: Dashboard")
- Connection status messages
- Color-coded status (green=connected, red=error, blue=info)

### Project Structure

```
VM-Harness/
├── gui/                          # PyQt5 GUI (25+ modules)
│   ├── __main__.py              # GUI entry point
│   ├── main_window.py           # Main window, title bar, sidebar, panel stack
│   ├── theme.py                 # Theme constants (colors, spacing, fonts)
│   ├── widgets.py               # Reusable widgets (Card, StatusIndicator, etc.)
│   ├── panels.py                # Dashboard panel
│   ├── panels_vm_switcher.py    # VM Switcher panel
│   ├── panels_vm_control.py     # VM Control panel
│   ├── panels_guest_terminal.py # Guest Terminal panel
│   ├── panels_guest_agent.py    # Guest Agent panel
│   ├── panels_telemetry.py      # Telemetry panel
│   ├── panels_sysinfo.py        # QMP System Info panel
│   ├── panels_qmp_console.py    # QMP Console panel
│   ├── panels_snapshots.py      # Snapshots panel
│   ├── panels_iso.py            # ISO Manager panel
│   ├── panels_wizard.py         # Create VM wizard panel
│   ├── panels_storage.py        # Storage panel
│   ├── panels_cpu.py            # CPU/Memory panel
│   ├── panels_display.py        # Display panel
│   ├── panels_qemu.py           # Advanced QEMU panel
│   ├── panels_usb.py            # USB & Devices panel
│   ├── panels_network.py        # Network panel
│   ├── panels_monitoring.py     # Monitoring panel
│   ├── panels_settings.py       # Settings panel
│   ├── panels_security.py       # Security panel
│   ├── panels_automation.py     # Automation panel
│   ├── panels_troubleshoot.py   # Troubleshoot panel
│   ├── panels_chat.py           # AI Chat panel
│   ├── panels_providers.py      # AI Providers panel
│   ├── panels_logs.py           # Logs panel
│   ├── panels_multi_vm_dashboard.py # Multi-VM Dashboard
│   ├── qmp_bridge.py            # QMP async bridge with PyQt5 signals
│   ├── ssh_bridge.py            # SSH async bridge
│   ├── chat_engine.py           # Agentic chat engine with tool executor
│   ├── api_providers.py         # API provider management
│   ├── provider_store.py        # Provider configuration store
│   ├── credential_store.py      # Encrypted credential vault
│   ├── iso_manager.py           # ISO file management
│   ├── multi_vm.py              # Multi-VM manager
│   ├── multi_vm_qmp_bridge.py   # Multi-VM QMP bridge
│   ├── snapshot_scheduler.py    # Snapshot scheduler
│   ├── metrics_store.py         # Metrics storage for telemetry
│   └── ...
├── tests/                        # Test suite
├── docs/                         # Documentation
│   ├── USER_GUIDE.md            # This file
│   ├── FAQ.md                   # Frequently asked questions
│   ├── TROUBLESHOOTING.md       # Troubleshooting guide
│   └── AGENT_GUIDE.md           # AI agent integration guide
├── .env                          # Configuration file (auto-generated)
├── pyproject.toml               # Project metadata and dependencies
└── README.md                    # Project overview
```

---

## 2. Installation

### Prerequisites

| Requirement | Minimum Version | Recommended | Notes |
|-------------|-----------------|-------------|-------|
| **Python** | 3.10 | 3.11 or 3.13 | 3.11+ required for async features |
| **QEMU** | 7.0 | 8.x+ | `qemu-system-x86_64.exe` on Windows |
| **Windows** | 10 | 11 | WHPX requires Windows 10 1903+ |
| **RAM** | 8 GB | 16 GB+ | 4 GB minimum for host + VM |
| **Disk Space** | 10 GB free | 50 GB+ | For VM images and application |
| **Git** | 2.30+ | Latest | For cloning repository |

**Recommended Windows Features:**
- **Windows Hypervisor Platform** — Required for WHPX acceleration
- **Virtual Machine Platform** — Required for WHPX acceleration
- **Hyper-V** (optional) — For additional virtualization features

**Enable Windows Features (PowerShell as Administrator):**
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
# Restart required
```

### Installing from Source

#### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/qemu-mcp.git
cd qemu-mcp
```

#### Step 2: Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
# source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
# Install with all dependencies including dev tools
pip install -e ".[dev]"
```

This installs:
- **PyQt5** — GUI framework (PyQt5 5.15+)
- **mcp[cli]** — Model Context Protocol server/client
- **pydantic + pydantic-settings** — Configuration validation
- **asyncssh** — SSH communication with guests
- **cryptography** — Fernet encryption for credential vault
- **matplotlib** — Real-time telemetry charts
- **psutil** — Process and system monitoring
- **aiohttp** — HTTP client for API communication
- **loguru** — Structured logging
- **pytest + pytest-asyncio** — Testing (dev only)

#### Step 4: Configure QEMU Path

Create or edit the `.env` file in the project root:

```env
# QEMU Configuration
QEMU_BINARY="C:/Program Files/qemu/qemu-system-x86_64.exe"
QEMU_EXTRA_ARGS="-machine q35,kernel_platform="

# VM Configuration
VM_NAME="omarchy-vm"
VM_DISK="C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2"
VM_ISO=""
VM_RAM_MB="16384"
VM_CPUS="8"
VM_HOSTNAME="omarchy-vm"

# Display
DISPLAY="SDL"
OPENGL="1"
AUTO_EJECT_ISO="1"

# Acceleration
VM_ACCELERATION="whpx"

# SSH/Network
SSH_HOST="127.0.0.1"
SSH_PORT="2222"
SSH_USERNAME="omarchyvm"

# Logging
LOG_LEVEL="INFO"
LOG_FILE=""

# Authentication
AUTH_METHOD="api_key"
```

#### Step 5: Verify Installation

```bash
# Check QEMU version
qemu-system-x86_64 --version

# Check Python dependencies
python -c "import PyQt5; print('PyQt5:', PyQt5.QtCore.PYQT_VERSION_STR)"

# Run status command
qemu-mcp status
```

#### Step 6: Run the Application

```bash
# Launch GUI
qemu-mcp gui
# or
python -m gui

# Launch CLI
qemu-mcp --help
```

### Installing the Executable (EXE)

A standalone Windows executable is available in the `dist/` directory as `VM-Harness.exe` (built via PyInstaller).

#### Installing the Pre-built Executable

1. **Download** the latest release from the releases page, or use the pre-built `dist/VM-Harness.exe`
2. **Extract** to a folder of your choice (e.g., `C:\VM-Harness\`)
3. **Run** `VM-Harness.exe` — no Python installation required
4. **Configure** QEMU path in Settings panel on first run

#### Building the Executable from Source

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable (consoleless Windows app)
pyinstaller --onefile --windowed --name VM-Harness gui/__main__.py

# Output: dist/VM-Harness.exe
```

**PyInstaller Options:**
- `--onefile` — Single executable file
- `--windowed` — No console window (GUI app)
- `--name VM-Harness` — Output filename

**The build includes:**
- All Python dependencies bundled
- PyQt5 GUI framework
- Application icon and resources

### Post-Installation Checklist

- [ ] QEMU binary path configured and verified
- [ ] Disk image exists at configured path
- [ ] RAM and CPU values set appropriately
- [ ] SSH port (2222) is available (not blocked by firewall)
- [ ] QMP port (4444) is available
- [ ] Windows Hypervisor Platform enabled (for WHPX)
- [ ] Application launches without errors

---

## 3. Quick Start Tutorial

### First VM Launch

This tutorial walks you through launching your first virtual machine.

#### Step 1: Launch the GUI

```bash
qemu-mcp gui
```

The main window opens with the **Dashboard** panel displayed by default.

#### Step 2: Verify Configuration

Before launching, verify your settings in the **Settings** panel:

1. Click **Settings** in the left sidebar
2. Check the **QEMU** tab:
   - QEMU Binary path is correct
   - Extra QEMU args are appropriate
3. Check the **VM** tab:
   - VM Name is set
   - Disk Path points to an existing qcow2 image
   - RAM and CPU values are appropriate

#### Step 3: Configure VM Resources

In the **Settings > VM** tab:

| Setting | Recommended Value |
|---------|-------------------|
| VM Name | `my-vm` |
| Disk Path | Path to your qcow2 image |
| RAM (MB) | 8192 (8 GB) |
| vCPUs | 4 |
| Hostname | `my-vm` |

#### Step 4: Start the VM

1. Return to the **Dashboard** panel
2. Click the **▶ Start VM** button
3. The status indicator turns green when the VM is running
4. View real-time stats: PID, RAM, vCPUs, Disk usage, Uptime

#### Step 5: Access the Guest

Once the VM is running:

1. **Guest Terminal** panel — SSH into the VM
   - Default username: `omarchyvm`
   - Default port: `2222`
   - Execute commands directly

2. **Guest Agent** panel — Manage files and processes
   - Browse files
   - Execute shell commands
   - Monitor processes

#### Step 6: Stop the VM

1. Click **■ Stop VM** on the Dashboard
2. Or use the CLI: `qemu-mcp vm stop my-vm`

### CLI Quick Commands

```bash
# System status
qemu-mcp status

# VM management
qemu-mcp vm list
qemu-mcp vm start my-vm
qemu-mcp vm stop my-vm
qemu-mcp vm restart my-vm

# Snapshots
qemu-mcp snapshot list
qemu-mcp snapshot create my-vm

# ISOs
qemu-mcp iso list

# Configuration
qemu-mcp config get

# Start REST API
qemu-mcp api start --port 8080
```

---

## 4. Panel Reference

VM-Harness includes 25+ panels organized by functionality. Each panel is accessed via the sidebar navigation. Below is a comprehensive reference for every panel.

---

### 4.1 Core VM Management

#### 1. Dashboard
**File:** `gui/panels.py`

**Description:** Main dashboard showing live VM status overview and quick actions. This is the default panel on application launch.

**Layout:**
- **VM Status Card** — Large status card showing VM state, PID, RAM, vCPUs, disk usage, and uptime
- **Status Indicator** — Colored dot (green=running, yellow=paused, gray=stopped/disconnected)
- **Quick Actions** — Three prominent buttons for common operations
- **Recent Activity** — Scrollable list of last 20 activities with timestamps

**Controls:**

| Control | Description | QMP Command |
|---------|-------------|-------------|
| **▶ Start VM** | Starts the virtual machine; disabled when VM is running | `cont` |
| **■ Stop VM** | Graceful shutdown via ACPI power button; disabled when VM is stopped | `system_powerdown` |
| **↻ Reset VM** | Warm reboot of the VM; disabled when VM is stopped | `system_reset` |

**Status Display:**

| Field | Description |
|-------|-------------|
| **State** | Running, Paused, Stopped, or Disconnected |
| **PID** | Process ID of the QEMU process (Windows: from tasklist) |
| **RAM** | Configured RAM in GB |
| **vCPUs** | Number of virtual CPUs |
| **Disk** | Disk space used |
| **Uptime** | Time since VM started (HH:MM:SS) |

**Activity Log:** Shows timestamped entries like "[14:23:01] VM start requested", "[14:23:05] VM stop requested", etc.

---

#### VM Switcher
**File:** `gui/panels_vm_switcher.py`

**Description:** Multi-VM management panel for adding, removing, and switching between multiple VM configurations.

**Layout:**
- **VM List** — ListWidget showing all registered VMs with status indicators (● running, ○ stopped)
- **Action Buttons** — Add, Switch, Remove, Start, Stop, Refresh, Clone, Templates
- **VM Details** — FormLayout showing selected VM's name, status, QMP URI, SSH URI, RAM, vCPUs
- **Resource Limits** — Grid layout with Max RAM, Max vCPUs, Priority spinboxes and Apply button
- **Status Bar** — Text showing current operation status

**Controls:**

| Control | Description |
|---------|-------------|
| **Add VM** | Opens dialog to register a new VM by selecting a disk image |
| **Switch To** | Sets the selected VM as the active VM for other panels |
| **Remove** | Unregisters a VM (configuration deleted, disk preserved) |
| **Start** | Starts the selected VM |
| **Stop** | Stops the selected VM |
| **Clone** | Opens CloneDialog to copy a VM's disk image |
| **Templates** | Opens TemplateManagerDialog for VM templates |
| **Apply Limits** | Applies resource limits (max RAM, max CPUs, priority) to selected VM |

**Resource Limits:**

| Limit | Range | Default | Description |
|-------|-------|---------|-------------|
| **Max RAM (MB)** | 512 - GLOBAL_MAX_RAM_MB | 4096 | Maximum memory the VM can use |
| **Max vCPUs** | 1 - GLOBAL_MAX_CPUS | 2 | Maximum CPU cores allocated |
| **Priority** | 1 - 10 | 5 | 1=highest priority, 10=lowest |

**Signals:**
- `vm_changed(str)` — Emitted when active VM changes
- `vm_added(str)` — Emitted when a VM is added
- `vm_removed(str)` — Emitted when a VM is removed

**Auto-refresh:** Timer polls every 5 seconds to update VM status.

---

#### VM Control
**File:** `gui/panels_vm_control.py`

**Description:** Full VM lifecycle control panel with hardware acceleration toggle and context-aware VM configuration display.

**Layout:**
- **Active VM Context Header** — Card showing which VM is being controlled with status dot
- **Hardware Acceleration Card** — WHPX toggle checkbox with status indicator and warning label
- **QMP Connection Card** — Connection status and Connect button
- **VM Lifecycle Control Card** — Six lifecycle buttons in a row
- **VM Configuration Card** — Grid display of VM's current settings (9 fields)
- **Progress Bar** — Hidden by default, shown during operations
- **Info Log** — Text display for operation results and errors

**Controls:**

| Control | Icon | Description | Tooltip |
|---------|------|-------------|---------|
| **Start** | 🟢 | Start the VM | "Start the virtual machine" |
| **Stop** | ⏹ | Graceful stop | "Gracefully stop the VM" |
| **Reset** | 🔄 | Warm reset | "Reset the VM (warm reboot)" |
| **Suspend** | ⏸ | Suspend to disk | "Suspend the VM to disk" |
| **Resume** | ▶ | Resume from suspend | "Resume a suspended VM" |
| **Eject ISO** | 💿 | Eject CD-ROM | "Eject the boot ISO" |

**Hardware Acceleration:**

| Mode | Description | Performance |
|------|-------------|-------------|
| **WHPX** (default) | Windows Hypervisor Platform | Best performance on Windows 10/11 |
| **HAXM** | Intel Hardware Accelerator | Good for Intel VT-x systems |
| **TCG** | Software emulation | Very slow (10-100x slower), no hardware required |

**Warning:** When TCG is selected, a warning label appears: "⚠️ Hardware acceleration disabled — VM will run in TCG (software) mode, which is significantly slower and not recommended for production workloads."

**VM Configuration Display Fields:**

| Field | Source |
|-------|--------|
| VM Name | `config.vm_name` |
| Status | `manager.get_status()` — running/paused/stopped |
| RAM | `config.ram_mb` MB |
| vCPUs | `config.cpus` |
| Disk Image | `config.disk_path` |
| QMP Port | `config.qmp_port` |
| SSH Port | `config.ssh_port` |
| QMP URI | `manager.get_qmp_uri()` |
| SSH URI | `manager.get_ssh_uri()` |

**Button State Logic:**
- Start: enabled when stopped or paused
- Stop: enabled when running or paused
- Reset: enabled when running
- Suspend: enabled when running
- Resume: enabled when paused
- Eject ISO: enabled when running

---

### 4.2 Guest Integration

#### Guest Terminal
**File:** `gui/panels_guest_terminal.py`

**Description:** SSH terminal and file browser for interactive guest VM access. Provides a split-view with terminal on the left and file browser on the right.

**Layout:**
- **SSH Connection Bar** — Status label, Connect button, Disconnect button
- **Terminal Panel** (left, 2/3 width) — TerminalOutput widget + command input row
- **File Browser Panel** (right, 1/3 width) — Navigation path, Upload/Refresh buttons, FileTree widget
- **Command History** — ListWidget with sample commands (ls, df, free, top, uname, cat)
- **Status Message** — Bottom status label

**Terminal Controls:**

| Control | Description |
|---------|-------------|
| **Command Input** | QLineEdit for typing shell commands; Enter to execute |
| **Send (▶)** | Executes the command in the input field |
| **Clear** | Clears terminal output |

**File Browser Controls:**

| Control | Description |
|---------|-------------|
| **Navigation Path** | Shows current directory path (e.g., `/home/omarchyvm`) |
| **Upload (⬆)** | Opens file dialog to upload a file to the guest |
| **Refresh (↻)** | Refreshes the file listing |
| **File Tree** | QTreeWidget showing guest filesystem; double-click to navigate directories |

**Sample Commands Provided:**
- `ls -la /home`
- `df -h`
- `free -m`
- `top -bn1 | head -20`
- `uname -a`
- `cat /etc/os-release`

**Requirements:**
- VM must be running
- SSH server must be running inside the guest
- Port forwarding configured (default: host 2222 → guest 22)

**SSH Bridge Integration:** Connects to SSHBridge for real command execution and file operations. Falls back to simulated output when SSH is not available.

---

#### Guest Agent
**File:** `gui/panels_guest_agent.py`

**Description:** QEMU guest agent management panel for guest introspection — processes, services, files, and network information.

**Layout:**
- **Header** — Title + Agent status label (Unknown/Connected/Disconnected/Error)
- **Tabs:** Guest Info, Processes, Services, File Browser, Network

**Tab Details:**

**Guest Info Tab:**
- QTreeWidget with guest properties: OS, Kernel, Hostname, Uptime, IP Addresses, Disk Usage, Memory, Load Average, QEMU Guest Agent status
- Refresh Info button

**Processes Tab:**
- QTableWidget with columns: PID, Name, CPU %, Memory %, Status
- Sample processes: systemd, qemu-ga, bash, firefox
- Kill Process button

**Services Tab:**
- QTableWidget with columns: Service, Status, Enabled, Description
- Sample services: sshd (Running), nginx (Stopped), docker (Running), firewalld (Running)

**File Browser Tab:**
- QLineEdit for path input + Go button
- QTreeWidget with columns: Name, Size, Modified, Type
- Sample files: Documents, Downloads, notes.txt, backup.tar.gz

**Network Tab:**
- QTextEdit showing network interfaces, routing, DNS, open ports
- Sample: eth0 (192.168.122.100/24), lo (127.0.0.1/8), default gateway, DNS servers, open ports (22/tcp sshd, 80/tcp nginx)

**SSH Bridge Integration:** When connected, fetches real data via SSH commands:
- Processes: `ps aux --no-headers | head -20`
- Services: `systemctl list-units --type=service --state=running --no-pager | head -10`
- Network: `ip addr show`
- Files: `list_dir(/home/omarchyvm)`

---

### 4.3 Monitoring & Telemetry

#### Telemetry
**File:** `gui/panels_telemetry.py`

**Description:** Real-time resource usage charts with historical data, alerts, and alerts log. Uses matplotlib for live charting.

**Layout:**
- **Tabs:** Live Charts, History, Alerts, Alerts Log

**Live Charts Tab:**
- 4 TelemetryChart widgets in a 2x2 grid:
  - CPU Usage (%)
  - Memory Usage (%)
  - Disk I/O (MB/s)
  - Network I/O (KB/s)
- Auto-updates every 2 seconds via QTimer

**History Tab:**
- Time Range selector (1h, 6h, 24h, 7d, 30d)
- Metric selector (cpu, mem, disk, net)
- Refresh button
- Export PNG button
- Historical TelemetryChart widget

**Alerts Tab:**
- QTableWidget for alert rules: Metric, Threshold, Condition, Action, Enabled

**Alerts Log Tab:**
- Log of fired/resolved alert history

**Depends on:** `gui.metrics_store` (optional — graceful degradation if not available)

---

#### QMP System Info
**File:** `gui/panels_sysinfo.py`

**Description:** Displays real QMP data from the VM with system information tree, raw QMP responses, and command reference.

**Layout:**
- **Header** — Title + Connection status label
- **Tabs:** System Info, Raw QMP, Command Reference
- **Auto-refresh Timer** — Polls every 5 seconds

**System Info Tab:**
- Card with QTreeWidget (Property, Value columns)
- Displays: VM name, UUID, QEMU version, KVM status, etc.

**Raw QMP Tab:**
- QTextEdit (read-only, Consolas font) showing raw JSON responses from QMP queries

**Command Reference Tab:**
- QTableWidget with 17 common QMP commands:
  - `query-status` — Get VM running status
  - `query-name` — Get VM name
  - `query-uuid` — Get VM UUID
  - `query-version` — Get QEMU version
  - `query-kvm` — Check KVM availability
  - `query-cpus` — List CPU information
  - `query-machines` — List supported machine types
  - `query-commands` — List all QMP commands
  - `system_powerdown` — Send ACPI power button event
  - `system_reset` — Reset the system
  - `stop` — Stop (pause) the VM
  - `cont` — Continue a paused VM
  - `eject` — Eject a CD-ROM device
  - `blockdev-add` — Add a block device
  - `device_add` — Add a device
  - `migrate` — Start migration
  - `snapshot-create` — Create a snapshot

**QMPDataCollector:** Background QThread that collects QMP data without blocking GUI. Collects: query-status, query-name, query-uuid, query-version, query-kvm.

---

#### QMP Console
**File:** `gui/panels_qmp_console.py`

**Description:** Direct QMP command console for power users who want to send arbitrary QMP commands and view raw JSON responses.

**Layout:**
- **Header** — Title + Status label (Disconnected/Connected)
- **Response Viewer** — Large QTextEdit (read-only, Consolas 10pt) for JSON responses
- **Preset Commands** — 7 buttons: Status, Name, KVM Info, UUID, Version, Commands, Target
- **Command Input** — QLineEdit with placeholder text showing example commands

**Preset Commands:**

| Button Label | QMP Command | Description |
|--------------|-------------|-------------|
| Status | `query-status` | Get VM running status |
| Name | `query-name` | Get VM name |
| KVM Info | `query-kvm` | Check KVM availability |
| UUID | `query-uuid` | Get VM UUID |
| Version | `query-version` | Get QEMU version |
| Commands | `query-commands` | List all available QMP commands |
| Target | `query-target` | Get target architecture |

**Command Input:**
- Type any QMP command (e.g., `query-status` or `{"execute": "system_powerdown"}`)
- Press Enter or click Send to execute

**Signals:** `command_sent(dict)` — Emitted when a command is sent

---

### 4.4 Storage & Snapshots

#### Snapshots
**File:** `gui/panels_snapshots.py`

**Description:** VM snapshot management — list, create, restore, and delete snapshots via qemu-img.

**Layout:**
- **Header** — Title + Snapshot count label
- **Snapshot List** — QListWidget showing snapshots (ID: name size_info)
- **Buttons** — Create, Restore, Delete, Refresh (all 90px wide)

**Controls:**

| Control | Description | Backend Command |
|---------|-------------|-----------------|
| **Create** | Prompts for snapshot name, creates snapshot | `qemu-img snapshot -c <name> <disk>` |
| **Restore** | Restores selected snapshot (with confirmation dialog) | `qemu-img snapshot -a <name> <disk>` |
| **Delete** | Deletes selected snapshot (with confirmation dialog) | `qemu-img snapshot -d <name> <disk>` |
| **Refresh** | Reloads snapshot list from qcow2 image | `qemu-img snapshot -l <disk>` |

**Disk Path:** Default is `C:\Users\Server\Virtual Machines\omarchy-vm\disk.qcow2`

**Confirmation Dialogs:**
- Restore: "Restore snapshot '{name}'? Current state will be lost."
- Delete: "Delete snapshot '{name}'? This cannot be undone."

**Error Handling:** QMessageBox.critical() on failure with error message from subprocess.

---

#### ISO Manager
**File:** `gui/panels_iso.py`

**Description:** Browse, import, and manage ISO files for VM installation. Supports internal storage, external folders, and common ISO downloads.

**Layout:**
- **Header** — Title + ISO count label
- **Tabs:** Available ISOs, External ISOs, Sources, Common ISOs

**Available ISOs Tab:**
- QTableWidget (5 columns): Name, Size, Source, Path, Actions
- Buttons: Refresh, Import ISO, Select for VM, Delete

**External ISOs Tab:**
- QTableWidget (5 columns): Filename, Size, Path, Source, Last Modified
- Buttons: Refresh, Browse External Folder, Remove Source, Select for VM

**Sources Tab:**
- Card with QListWidget showing external source folders
- Buttons: Add Folder, Remove

**Common ISOs Tab:**
- Card with QTableWidget (4 columns): Name, Size, URL, Action
- Pre-populated from `COMMON_ISOS` dictionary

**Controls:**

| Control | Description |
|---------|-------------|
| **Refresh** | Rescans all ISO sources and repopulates tables |
| **Import ISO** | Copies ISO from local filesystem to internal storage via `ISOManager.copy_to_internal()` |
| **Select for VM** | Emits `iso_selected` signal with ISO path |
| **Delete** | Deletes internal ISO (only works for internal source ISOs) |
| **Browse External Folder** | Adds a folder as an external ISO source via `ISOManager.add_external_source()` |
| **Remove Source** | Removes an external source folder |

**ISO Sources:** Internal (green text) vs External (yellow text)

---

#### Create VM (Wizard)
**File:** `gui/panels_wizard.py`

**Description:** 5-step VM creation wizard for provisioning new virtual machines with guided configuration.

**Layout:**
- **Header** — "Create New Virtual Machine" title
- **Progress Bar** — Shows step X of 5
- **Stacked Widget** — 5 pages, one per step
- **Navigation Buttons** — Back, Next/Create

**Steps:**

**Step 1: Identity (`_step_identity`)**
- VM Name (QLineEdit)
- Operating System (QComboBox: Linux, Windows, macOS, BSD, Other)
- Machine Type (QComboBox: q35 (modern PC), pc (legacy PC), virt (ARM))
- Firmware (QComboBox: OVMF (UEFI), SeaBIOS (Legacy BIOS))

**Step 2: Hardware (`_step_hardware`)**
- Number of CPUs (QSpinBox: 1-128, default 2)
- Memory (QSpinBox: 256-131072 MB, default 4096 MB)
- Host CPU passthrough (QCheckBox)
- I/O Threads (QSpinBox: 1-8, default 1)

**Step 3: Storage (`_step_storage`)**
- Disk Size (QSpinBox: 1-2048 GB, default 40 GB)
- Disk Format (QComboBox: qcow2 (recommended), raw, vmdk, vhd)
- Cache Mode (QComboBox: writeback, writethrough, none, unsafe)
- Installation ISO (QLineEdit + Browse button, optional)

**Step 4: Network (`_step_network`)**
- Network Mode (QComboBox: NAT (user mode), Bridged, Isolated)
- Port Forwards (QTextEdit, one per line: "2222 → 22")

**Step 5: Confirm (`_step_confirm`)**
- QTextEdit showing configuration summary
- Create VM button

**Navigation:**
- Back button: disabled on step 1
- Next button: shown on steps 1-4, hidden on step 5
- Create VM button: shown on step 5 only

**VM Creation:**
- Creates directory: `~/Virtual Machines/<vm-name>/`
- Creates disk: `qemu-img create -f <format> <path> <size>G`
- Shows QMessageBox.information on success

---

#### Storage
**File:** `gui/panels_storage.py`

**Description:** Disk image management — create, resize, convert, and delete virtual disks.

**Layout:**
- **Header** — Title
- **Disk List** — QListWidget showing VMs with disk paths and sizes (scans `~/Virtual Machines/`)
- **Buttons** — Create Disk, Resize, Convert, Delete, Refresh (all 90-110px wide)

**Controls:**

| Control | Description | Backend Command |
|---------|-------------|-----------------|
| **Create Disk** | Creates new virtual disk with name, size, format | `qemu-img create -f <fmt> <path> <size>G` |
| **Resize** | Resizes selected disk to new size | `qemu-img resize <path> <size>G` |
| **Convert** | Converts disk to different format | `qemu-img convert -f qcow2 -O <target> <src> <dst>` |
| **Delete** | Deletes selected disk (with confirmation) | `Path(disk_path).unlink()` |
| **Refresh** | Scans `~/Virtual Machines/` for qcow2 disks | — |

**Create Disk Dialog:**
- Disk name (without extension)
- Size in GB (1-2048, default 40)
- Format (qcow2, raw, vmdk, vhd)

**Convert Dialog:**
- Target format selection

**Error Handling:** QMessageBox.critical() on subprocess failures or file operation errors.

---

### 4.5 Hardware Configuration

#### CPU/Memory
**File:** `gui/panels_cpu.py`

**Description:** CPU and memory configuration panel with hotplug, NUMA topology, and ballooning settings.

**Layout:**
- **Header** — Title
- **Tabs:** CPU, Memory, NUMA

**CPU Tab:**
- Card with QGridLayout form:
  - Sockets (QSpinBox: 1-4, default 1)
  - Cores per socket (QSpinBox: 1-128, default 4)
  - Threads per core (QSpinBox: 1-2, default 1)
  - Host CPU passthrough checkbox

**Memory Tab:**
- Card with QGridLayout form:
  - Current Memory (QSpinBox: 256-131072 MB, default 4096 MB)
  - Enable memory hotplug checkbox
  - Enable virtio-balloon (dynamic memory) checkbox

**NUMA Tab:**
- Card with QTextEdit showing NUMA topology:
  ```
  NUMA Node 0:
    CPUs: 0-3
    Memory: 4096 MB
    Distance: 10
  ```

---

#### Display
**File:** `gui/panels_display.py`

**Description:** Display configuration and remote access settings panel with GPU/3D configuration.

**Layout:**
- **Header** — Title
- **Tabs:** Display, Remote Access, GPU / 3D

**Display Tab:**
- Card with QGridLayout:
  - Type (QComboBox: SDL, GTK, VNC, SPICE, None)
  - Resolution (QComboBox: Auto, 1920x1080, 2560x1440, 3840x2160, Custom)

**Remote Access Tab:**
- VNC Server card with Port (QSpinBox: 5900-5999, default 5900)
- SPICE Server card with Port (QSpinBox: 5930-5999, default 5930)

**GPU / 3D Tab:**
- Card with GPU Type (QComboBox: None, VirGL (virtio-vga), GPU Passthrough (vfio-pci), NVIDIA vGPU)

---

#### Advanced QEMU
**File:** `gui/panels_qemu.py`

**Description:** Advanced QEMU configuration panel with machine settings, boot order, SMBIOS, and QMP log.

**Layout:**
- **Header** — Title
- **Tabs:** Machine, Boot, SMBIOS, QMP Log

**Machine Tab:**
- Card with QGridLayout:
  - Machine Type (QComboBox: q35, pc, virt, virt-2.0, isapc)
  - CPU Model (QComboBox: host, qemu64, kvm64, Broadwell, Skylake; editable)
  - Firmware (QComboBox: OVMF (UEFI), SeaBIOS (Legacy), AAVMF (ARM UEFI))

**Boot Tab:**
- Card with QGridLayout:
  - Boot Order (QTextEdit, default "c d n", max height 50)
  - Enable PXE boot checkbox

**SMBIOS Tab:**
- Card with QGridLayout for 5 fields:
  - Manufacturer (default: "QEMU")
  - Product (default: "Standard PC")
  - Version (default: "pc-q35-7.2")
  - Serial (default: "1234567890")
  - UUID (default: "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

**QMP Log Tab:**
- Card with QTextEdit (read-only, Consolas 11pt) for QMP communication log
- Command input row: QLineEdit + Send button
- Placeholder: "Enter QMP command (e.g., query-status)"

---

#### USB & Devices
**File:** `gui/panels_usb.py`

**Description:** USB device passthrough, PCI passthrough, and TPM/Secure Boot configuration panel.

**Layout:**
- **Header** — Title
- **Tabs:** USB Devices, PCI Passthrough, TPM / Secure Boot

**USB Devices Tab:**
- Search/filter bar with QLineEdit (placeholder: "Filter by vendor, product, serial, bus, device..."), Clear button, Refresh button
- QTableWidget (8 columns): Vendor, Product, Serial, Bus, Device, Vendor Name, Product Name, Assigned
- Status label
- Action buttons: Attach to VM, Detach
- Auto-attach on VM start checkbox

**USB Enumeration:**
- Uses WMI via `wmi` Python package (Windows)
- Falls back to PowerShell CIM enumeration
- Falls back to sample devices list if WMI unavailable

**Sample Devices:**
- Logitech Unifying Receiver (046d:c52b)
- SanDisk Ultra USB 3.0 (0781:5567)
- Apple iPhone (05ac:12a8)
- STMicroelectronics ST-Link V2 (0483:5740)

**Attach/Detach:**
- Builds QMP `device_add`/`device_del` commands with `usb-host` driver
- Includes vendorid, productid, bus, id, and serial (if available)
- Updates device assigned status in UI

**PCI Passthrough Tab:**
- QTableWidget (5 columns): Address, Vendor, Device, Class, Status
- Sample devices: Intel HD Graphics 630, NVIDIA RTX 3080, Intel NVMe SSD
- Buttons: Passthrough to VM, Release

**TPM / Secure Boot Tab:**
- Card with configuration options:
  - Enable vTPM 2.0 checkbox (required for Windows 11)
  - Enable UEFI Secure Boot checkbox

**Config Persistence:** Saves to `~/.qemu-mcp/usb_config.json` with favorites, auto_attach, filter_history.

---

### 4.6 Networking

#### Network
**File:** `gui/panels_network.py`

**Description:** Virtual network, port forwarding, and firewall management panel with three tabs.

**Layout:**
- **Header** — Title
- **Tabs:** Virtual Networks, Port Forwarding, Firewall Rules

**Virtual Networks Tab:**
- QTableWidget (5 columns): Name, Type, Subnet, Gateway, Status
- Buttons: Add Network, Delete

**Add Network Dialog:**
- Network name
- Network type (QComboBox: NAT, Bridged, Isolated)

**Port Forwarding Tab:**
- QTableWidget (5 columns): VM, Protocol, Host Port, Guest Port, Enabled
- Buttons: Add Rule, Delete

**Add Port Forward Dialog:**
- VM name
- Protocol (QComboBox: TCP, UDP)
- Host port (QSpinBox: 1-65535, default 2222)
- Guest port (QSpinBox: 1-65535, default 22)

**Firewall Rules Tab:**
- QTableWidget (6 columns): Chain, Source, Destination, Port, Action, Enabled
- Buttons: Add Rule, Delete

---

### 4.7 Automation & Monitoring

#### Automation
**File:** `gui/panels_automation.py`

**Description:** Automation, scripting, and scheduling panel with macros, schedules, and event hooks.

**Layout:**
- **Header** — Title
- **Tabs:** Macros, Schedules, Hooks

**Macros Tab:**
- QTableWidget (4 columns): Name, Commands, Last Run, Status
- Sample macros: "Daily Backup" (snapshot create daily), "Cleanup" (snapshot delete old)
- Buttons: Add Macro, Run

**Schedules Tab:**
- QTableWidget (5 columns): Name, Schedule, Action, Enabled, Next Run

**Hooks Tab:**
- QTableWidget (4 columns): Event, Script, Enabled, Last Triggered
- Sample hooks: "VM Start" → `/scripts/vm-start.sh`, "VM Stop" → `/scripts/vm-stop.sh`

---

#### Monitoring
**File:** `gui/panels_monitoring.py`

**Description:** Real-time monitoring and alerting panel with metrics charts, alert rules, and log explorer.

**Layout:**
- **Header** — Title
- **Tabs:** Real-time Metrics, Alerts, Log Explorer

**Real-time Metrics Tab:**
- 4 TelemetryChart widgets in 2x2 grid:
  - CPU Usage (%)
  - Memory Usage (%)
  - Disk I/O (MB/s)
  - Network I/O (KB/s)
- Auto-updates every 2 seconds

**Alerts Tab:**
- QTableWidget (5 columns): Metric, Threshold, Condition, Action, Enabled

**Log Explorer Tab:**
- Log exploration interface

---

### 4.8 System & Configuration

#### Settings
**File:** `gui/panels_settings.py`

**Description:** Comprehensive settings panel with all configurable options organized by category tabs. Saves to .env file with validation.

**Layout:**
- **Tab Widget** — 9 tabs: QEMU, VM, Display, Acceleration, Network, Logging, Snapshots, Auth, (Snapshots scheduler embedded)
- **Save/Reset/Refresh Buttons** — Save Settings, Reset to Defaults, Refresh from .env
- **Status Label** — Shows save status messages

**QEMU Tab:**
- QEMU Binary (TextInput, default: `C:/Program Files/qemu/qemu-system-x86_64.exe`)
- Extra QEMU Args (TextInput, default: `-machine q35,kernel_platform=`)

**VM Tab:**
- VM Name (TextInput, default: `omarchy-vm`)
- Disk Path (TextInput, default: `C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2`)
- ISO Path (TextInput, default: `(no ISO — disk has OS installed)`)
- RAM (QSpinBox: 512-65536, default 16384)
- vCPUs (QSpinBox: 1-128, default 8)
- Hostname (TextInput, default: `omarchy-vm`)

**Display Tab:**
- Display Type (QComboBox: SDL, GTK, VNC, Spice, None; default SDL)
- OpenGL (QCheckBox, default checked)
- Auto-eject ISO (QCheckBox, default checked)

**Acceleration Tab:**
- Acceleration Mode (QComboBox: whpx, haxm, tcg; default whpx)
- Description label explaining each mode
- Warning label shown when TCG selected

**Network Tab:**
- SSH Host (TextInput, default: `127.0.0.1`)
- SSH Port (QSpinBox: 1-65535, default 2222)
- Guest Username (TextInput, default: `omarchyvm`)

**Logging Tab:**
- Log Level (QComboBox: DEBUG, INFO, WARNING, ERROR, CRITICAL; default INFO)
- Log File (TextInput, default empty)

**Auth Tab:**
- Auth Method (QComboBox: api_key, none, jwt; default api_key)
- API Key status: "Stored securely — use Security tab"

**Validation on Save:**
- QEMU binary must exist as file
- Disk must exist as file
- SSH port must be 1-65535
- RAM must be 256-131072 MB
- CPUs must be 1-128

**Save Behavior:** Merges with existing .env, writes sorted keys, sets file permissions to 0o600.

---

#### Security
**File:** `gui/panels_security.py`

**Description:** Encrypted credential vault management panel with secure add/edit/delete/view operations.

**Layout:**
- **Stats Bar** — Credential count + types list
- **Split View** — Credential list (left, 3/4) + Detail panel (right, 1/4)
- **Action Bar** — Add Credential button, Search input, Clear All button

**Credential List (left):**
- QTreeWidget with columns: Name, Type, Description, Updated
- Double-click to view details
- Type column color-coded: password (orange), ssh_key (purple), api_key (green), qmp_pass (blue), other (gray)

**Credential Details (right):**
- Name label (bold)
- Type label
- Description label
- Updated label
- Value label (masked: first 2 + *** + last 2 chars)
- Edit button, Delete button, Copy Value (masked) button

**Add Credential Dialog (`CredentialDialog`):**
- Form layout with:
  - Name (required)
  - Type (QComboBox: password, ssh_key, api_key, qmp_pass, other)
  - Secret Value (required, password echo mode)
  - Description (optional)
- Save/Cancel buttons
- If editing: prompts to confirm showing current value

**Encryption:** Uses Fernet symmetric encryption from `cryptography` library. Values never exposed in plaintext outside add/edit dialog.

**Auto-refresh:** Timer refreshes list every 5 seconds.

---

#### Logs
**File:** `gui/panels_logs.py`

**Description:** Tabbed log viewer for Application, QMP, and SSH logs with filtering, search, and export capabilities.

**Layout:**
- **Toolbar** — Log source combobox, level filter checkboxes (5), Clear button, Export button
- **Tab Widget** — 3 tabs: Application, QMP, SSH
- **Status Bar** — Shows current log source and entry count

**Log Source Selector:**
- Application, QMP, SSH

**Level Filters:**
- DEBUG, INFO, WARNING, ERROR, CRITICAL (all checked by default)

**Log Tabs:**
Each tab has a QTextBrowser (read-only, Consolas font, dark background) showing timestamped, color-coded log entries.

**Color Coding:**
- DEBUG: #64748b (slate)
- INFO: #38bdf8 (blue)
- WARNING: #f59e0b (amber)
- ERROR: #ef4444 (red)
- CRITICAL: #dc2626 (dark red)

**Sample Logs:**
- Application: 10 entries (startup, config loading, client initialization, panel loading)
- QMP: 6 entries (connection, capabilities, status queries)
- SSH: 5 entries (connection init, host keys, auth method, timeouts)

**Actions:**
- Clear: Clears current log view
- Export: Exports current log view to timestamped .txt file

---

#### Troubleshoot
**File:** `gui/panels_troubleshoot.py`

**Description:** VM diagnostics and debugging tools panel with diagnostics, GDB debugger, and debug logs.

**Layout:**
- **Header** — Title
- **Tabs:** Diagnostics, GDB Debugger, Debug Logs

**Diagnostics Tab:**
- Card with QTextEdit (read-only, Consolas 11pt) for diagnostic output
- Run Diagnostics button
- Sample output:
  ```
  Running diagnostics...
  ✓ QMP connection: OK
  ✓ Disk space: OK
  ✓ Network: OK
  ✓ Memory: OK
  ```

**GDB Debugger Tab:**
- Card with GDB Port (QLineEdit, default: "1234")
- QTextEdit (read-only) for GDB console output

**Debug Logs Tab:**
- Card with QTextEdit (read-only) for QEMU debug logs
- Enable Debug button

---

### 4.9 Chat & AI Integration

#### AI Chat
**File:** `gui/panels_chat.py`

**Description:** Built-in agentic chat panel with QEMU tool execution. Allows natural language VM control via LLM.

**Layout:**
- **Header** — Title + Provider dropdown (QComboBox)
- **Splitter** (vertical) — Chat display (top) + Input area (bottom)
- **Chat Display** — QTextEdit (read-only, Consolas 10pt, dark background #0d1117)
- **Input Area** — QLineEdit + Send button + Clear button
- **Welcome Messages** — System messages explaining capabilities

**Chat Display Format:**
- Timestamped messages with colored role labels:
  - User: brand color
  - AI: success (green) color
  - Tool: warning (orange) color
  - System: muted color

**Tool Execution Display:**
- Expandable tool widgets showing:
  - Tool icon + name
  - Status (running/done/failed)
  - Args summary (first 80 chars)
  - Collapsed: args summary only
  - Expanded: full arguments + result (truncated to 2000 chars)

**Tool Icons:**
- vm_status: 📊, vm_start: ▶️, vm_stop: ⏹️, vm_reset: 🔄, vm_suspend: ⏸️, vm_resume: ▶️
- guest_exec: 💻, snapshot_create: 📸, snapshot_list: 📋, snapshot_restore: ⏪
- iso_list: 💿, iso_import: 📥, get_usage: 📈

**Provider Dropdown:**
- Populated from `ProviderStore.get_enabled_providers()`
- Shows "No providers configured" if none available

**Chat Engine Integration:**
- Uses `ChatEngine` with `ToolExecutor`
- ToolExecutor has: qmp_bridge, ssh_bridge, iso_manager
- Engine signals: `tool_call_started`, `tool_call_finished`

**Clear History:**
- Clears chat display, engine history, and tool widgets
- Shows "Chat history cleared." system message

---

#### AI Providers
**File:** `gui/panels_providers.py`

**Description:** AI provider configuration panel for managing API keys, models, and provider settings.

**Layout:**
- **Header** — Title + Refresh button
- **Provider Table** — QTableWidget (5 columns): Provider, Model, API Key, Enabled, Priority
- **Buttons** — Set API Key, Add Custom
- **Usage Summary** — GroupBox with total requests, cost, tokens, success rate

**Provider Table:**

| Column | Description |
|--------|-------------|
| Provider | Provider name (e.g., OpenRouter, Anthropic) |
| Model | Model name (e.g., gpt-4, claude-3-opus) |
| API Key | Masked as "••••••••" or "Not set" |
| Enabled | "Yes" or "No" |
| Priority | Numeric priority value |

**Set API Key:**
- Prompts for selected provider's API key via QInputDialog (password mode)
- Calls `ProviderStore.set_api_key()`
- Shows success message box

**Add Custom Provider:**
- Prompts for: Provider name, Base URL, Model name, API key (optional)
- Creates `ProviderConfig` and adds via `ProviderStore.add_provider()`

**Usage Summary:**
- Shows: Requests, Cost ($), Tokens, Success rate (%)
- Updated from `ProviderStore.get_usage_summary()`

---

### 4.10 Additional Panels

#### Logs Panel
See section 4.8 (System & Configuration) for full details.

#### Multi-VM Dashboard
**File:** `gui/panels_multi_vm_dashboard.py`

**Description:** Overview dashboard showing all managed VMs with status summaries and quick actions.

**Features:**
- List of all VMs with status indicators
- Per-VM status summary cards
- Quick action buttons for each VM
- Resource aggregation across all VMs

---

## 5. Agentic AI Chat Usage

The Agentic Chat panel allows you to control your QEMU virtual machine using natural language. The chat engine integrates with AI API providers to understand your requests and execute QEMU tools automatically.

### Overview

| Feature | Description |
|---------|-------------|
| Natural Language Control | Type requests like "Is my VM running?" or "Start my VM" |
| Tool Execution | AI executes QMP, SSH, and ISO tools automatically |
| Multi-Provider Support | Switch between OpenRouter, Anthropic, OpenAI, Google |
| Chat History | Conversation history maintained within the session |
| Tool Display | Expandable widgets showing arguments and results |

### Configure API Keys

Before using chat, you must configure at least one API provider:

1. Open **Settings > AI Providers** (or the **API Providers** panel)
2. Add your API key for your chosen provider
3. Enable the provider
4. Return to the Chat panel and select the provider from the dropdown

See [Section 6: API Provider Configuration](#6-api-provider-configuration) for detailed setup instructions.

### Using the Chat Interface

**Chat Display:**
- QTextEdit with Consolas 10pt font on dark background
- Timestamped messages with colored role labels:
  - **User:** Brand color
  - **AI:** Green (#22c55e)
  - **Tool:** Orange (#f59e0b)
  - **System:** Muted gray

**Input Area:**
- QLineEdit for typing natural language requests
- Send button (or press Enter) to submit
- Clear button to reset chat history

**Tool Execution Display:**
- Expandable tool widgets showing:
  - Tool icon + name
  - Status (running/done/failed)
  - Args summary (collapsed) or full arguments + result (expanded, truncated to 2000 chars)

**Tool Icons:**
- vm_status: 📊, vm_start: ▶️, vm_stop: ⏹️, vm_reset: 🔄, vm_suspend: ⏸️, vm_resume: ▶️
- guest_exec: 💻, snapshot_create: 📸, snapshot_list: 📋, snapshot_restore: ⏪
- iso_list: 💿, iso_import: 📥, get_usage: 📈

### Available Tools

| Tool | Description | Example Prompt |
|------|-------------|----------------|
| `vm_status` | Get VM status (state, PID, RAM, vCPUs) | "Is my VM running?" |
| `vm_start` | Start the VM via QMP `cont` | "Start my virtual machine" |
| `vm_stop` | Stop the VM via QMP `system_powerdown` | "Shut down the VM" |
| `vm_reset` | Reset the VM via QMP `system_reset` | "Restart the VM" |
| `vm_suspend` | Suspend VM to disk | "Pause the VM" |
| `vm_resume` | Resume a suspended VM | "Resume the VM" |
| `guest_exec` | Execute a command in the guest via SSH | "Run uname -a in the guest" |
| `guest_file_read` | Read a file from the guest | "Show me /etc/os-release" |
| `guest_file_write` | Write content to a file in the guest | "Create a config file" |
| `guest_file_list` | List files in a guest directory | "List /tmp directory" |
| `guest_file_remove` | Delete a file in the guest | "Delete the temp file" |
| `snapshot_create` | Create a VM snapshot | "Take a snapshot named backup" |
| `snapshot_list` | List existing snapshots | "What snapshots exist?" |
| `snapshot_restore` | Restore a VM snapshot | "Restore the backup snapshot" |
| `iso_list` | List available ISO files | "What ISOs are available?" |
| `iso_import` | Import an ISO file | "Import this ISO file" |
| `get_usage` | Get VM resource usage stats | "How much RAM is used?" |

### Chat Examples

**Check VM Status:**
```
You: Is my VM running?
AI: Let me check the status of your VM.
[Tool: vm_status]
→ {"return": {"status": "running", "pid": 12345, "ram_mb": 16384}}
AI: Your VM "omarchy-vm" is currently running.
  - PID: 12345
  - RAM: 16 GB
  - vCPUs: 8
  - State: running
```

**Start the VM:**
```
You: Start my virtual machine
AI: I'll start the VM for you.
[Tool: vm_start]
→ {"return": {"status": "success"}}
AI: The VM has been started successfully.
```

**Execute a Guest Command:**
```
You: Run df -h in the guest
AI: I'll execute that command in the guest.
[Tool: guest_exec(command="df -h")]
→ Filesystem      Size  Used Avail Use% Mounted on
   /dev/sda1       20G  5.2G   15G  26% /
AI: Here's the disk usage for your VM.
```

**Create a Snapshot:**
```
You: Create a snapshot called before-update
AI: Creating snapshot "before-update"...
[Tool: snapshot_create(name="before-update")]
→ Snapshot created successfully
AI: Snapshot "before-update" has been created.
```

**List ISOs:**
```
You: What ISOs do I have available?
AI: Let me check your ISO library.
[Tool: iso_list]
→ [{'name': 'ubuntu-22.04.iso', 'size': '3.2 GB'},
   {'name': 'windows-11.iso', 'size': '5.4 GB'}]
AI: You have 2 ISOs available:
  1. ubuntu-22.04.iso (3.2 GB)
  2. windows-11.iso (5.4 GB)
```

### Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "No provider configured" | No API key set in Providers panel | Go to API Providers panel and configure an API key |
| "VM not running" | VM is stopped | Start the VM first |
| "SSH unreachable" | No SSH server in guest | Install SSH server in guest |
| "QMP disconnected" | QMP connection lost | Restart VM or check QMP settings |
| "Tool error" | Tool-specific failure | Check error message details |
| "Provider API error" | AI provider error | Check API key, quota, and internet connection |

### Tips for Effective Chat Usage

1. **Be specific** — "Start my VM" works better than "do stuff"
2. **Chain commands** — "Start my VM and then run df -h"
3. **Use natural language** — The AI understands conversational requests
4. **Check tool output** — Tool widgets show exactly what was executed
5. **Clear when needed** — Reset the chat if the conversation gets confused

---

## 6. API Provider Configuration

#### 2. VM Switcher (`panels_vm_switcher.py`)
**Description:** Multi-VM management — add, remove, and switch between VMs.

**Features:**
- List of configured VMs
- Add new VM profiles
- Remove existing VMs
- Quick switch between VMs

---

#### 3. VM Control (`panels_vm_control.py`)
**Description:** Full VM lifecycle control panel.

**Features:**
- Start/Stop/Restart VM
- Suspend/Resume VM
- Eject ISO from CD-ROM
- Boot device configuration
- Force shutdown option

**Controls:**
- Start, Stop, Restart, Suspend, Resume buttons
- ISO eject button
- Boot order selector

---

### 4.2 Guest Integration

#### 4. Guest Terminal (`panels_guest_terminal.py`)
**Description:** SSH command execution with history.

**Features:**
- Interactive SSH terminal
- Command history (up/down arrows)
- Session persistence
- Connection status indicator

**Requirements:**
- VM must be running
- SSH server must be running inside guest
- Port forwarding configured (default: 2222 → 22)

---

#### 5. Guest Agent (`panels_guest_agent.py`)
**Description:** Guest process, service, and file management via SSH.

**Features:**
- Execute shell commands
- File browser
- Process list
- Service management

**Operations:**
- Run commands: `uname -a`, `df -h`, `ps aux`
- Browse directories
- Read/write files

---

### 4.3 Monitoring & Telemetry

#### 6. Telemetry (`panels_telemetry.py`)
**Description:** Real-time CPU, RAM, Disk, and Network charts.

**Features:**
- Live CPU usage chart (matplotlib)
- RAM usage over time
- Disk I/O metrics
- Network throughput

**Visualization:** Line charts updated in real-time showing resource consumption trends.

---

#### 7. QMP System Info (`panels_sysinfo.py`)
**Description:** Real QMP data display — status, version, KVM info, command reference.

**Features:**
- VM status from QMP
- QEMU version information
- KVM acceleration status
- Available QMP commands reference

---

#### 8. QMP Console (`panels_qmp_console.py`)
**Description:** Direct QMP command input with JSON response viewer.

**Features:**
- Command input field
- JSON response display
- Command history
- Send arbitrary QMP commands

**Example Commands:**
- `query-status` — Get VM status
- `query-commands` — List available commands
- `system_powerdown` — Graceful shutdown

---

### 4.4 Storage & Snapshots

#### 9. Snapshots (`panels_snapshots.py`)
**Description:** Create, restore, and delete VM snapshots via qemu-img.

**Features:**
- Snapshot list with IDs and names
- Create new snapshot (named)
- Restore selected snapshot
- Delete snapshot
- Refresh list

**Operations:**
- **Create:** `qemu-img snapshot -c <name> <disk>`
- **Restore:** `qemu-img snapshot -a <name> <disk>`
- **Delete:** `qemu-img snapshot -d <name> <disk>`

---

#### 10. ISO Manager (`panels_iso.py`)
**Description:** Browse, import, and download ISO files.

**Features:**
- Internal storage display
- External folder scanning
- ISO downloader integration
- Import from local filesystem

---

#### 11. Create VM (`panels_wizard.py`)
**Description:** 5-step VM provisioning wizard.

**Steps:**
1. Name and basic config
2. Disk selection/creation
3. ISO selection (optional)
4. Resource allocation (RAM, CPU)
5. Review and create

---

#### 12. Storage (`panels_storage.py`)
**Description:** Disk create, resize, convert, and delete operations.

**Features:**
- Create new qcow2 disks
- Resize existing disks
- Convert between formats
- Delete disks

---

### 4.5 Hardware Configuration

#### 13. CPU/Memory (`panels_cpu.py`)
**Description:** Hotplug, CPU pinning, NUMA, and ballooning configuration.

**Features:**
- CPU hotplug support
- Memory ballooning
- NUMA configuration
- CPU model selection

---

#### 14. Display (`panels_display.py`)
**Description:** VNC, SPICE, RDP, and GPU configuration.

**Features:**
- Display backend selection (SDL, GTK, VNC, Spice, None)
- OpenGL enable/disable
- VNC port configuration
- Spice channel setup

---

#### 15. Advanced QEMU (`panels_qemu.py`)
**Description:** Machine type, boot order, SMBIOS settings.

**Tabs:**
- **Machine:** Machine type, CPU model, firmware selection
- **Boot:** Boot order, PXE boot enable
- **SMBIOS:** Manufacturer, Product, Version, Serial, UUID
- **QMP Log:** QMP communication log viewer

---

#### 16. USB/Devices (`panels_usb.py`)
**Description:** USB passthrough, PCI passthrough, TPM 2.0 configuration.

**Tabs:**
- **USB Devices:** List, filter, attach/detach USB devices
- **PCI Passthrough:** GPU, NVMe, and other PCI device passthrough
- **TPM/Secure Boot:** vTPM 2.0 and UEFI Secure Boot settings

**USB Features:**
- WMI-based device enumeration (Windows)
- Search/filter by vendor, product, serial
- Attach/detach via QMP `device_add`/`device_del`
- Auto-attach on VM start option
- Config persistence

---

### 4.6 Networking

#### 17. Network (`panels_network.py`)
**Description:** Virtual networks, port forwarding, and firewall management.

**Tabs:**
- **Virtual Networks:** Create/manage NAT, Bridged, Isolated networks
- **Port Forwarding:** Add/delete port forward rules (Host → Guest)
- **Firewall Rules:** Chain, source, destination, port, action rules

---

#### 18. Network Editor (`panels_network_editor.py`)
**Description:** Advanced network configuration editor.

**Features:**
- Network topology visualization
- Detailed network parameter editing
- Bridge configuration
- VLAN setup

---

### 4.7 Automation & Monitoring

#### 19. Automation (`panels_automation.py`)
**Description:** Macros, schedules, and event hooks.

**Features:**
- Macro recording and playback
- Scheduled tasks
- Event-driven hooks
- Automation script editor

---

#### 20. Monitoring (`panels_monitoring.py`)
**Description:** Real-time metrics, alerts, and log explorer.

**Features:**
- Live metrics dashboard
- Alert configuration
- Log exploration
- Historical data review

---

### 4.8 System & Configuration

#### 21. Settings (`panels_settings.py`)
**Description:** Full `.env` editor with validation.

**Tabs:**
- **QEMU:** Binary path, extra args
- **VM:** Name, disk, ISO, RAM, CPUs, hostname
- **Display:** Display type, OpenGL, auto-eject ISO
- **Acceleration:** WHPX, HAXM, TCG mode selection
- **Network:** SSH host, port, guest username
- **Logging:** Log level, log file path
- **Snapshots:** Snapshot scheduler settings
- **Auth:** Authentication method, API key management

**Validation:**
- QEMU binary existence check
- Disk file existence check
- Port range validation
- RAM/CPU range validation

---

#### 22. Security (`panels_security.py`)
**Description:** Encrypted credential vault, user management, audit log.

**Features:**
- Credential CRUD (add, edit, delete, view)
- Fernet encryption for stored secrets
- Credential types: password, ssh_key, api_key, qmp_pass
- Search and filter credentials
- Masked value display
- Clear all credentials

**Credential Dialog:**
- Name (required)
- Type selection
- Secret value (required)
- Description (optional)

---

#### 23. Logs (`panels_logs.py`)
**Description:** Filterable, searchable, exportable log viewer.

**Features:**
- Log level filtering
- Text search
- Export to file
- Timestamp display

---

#### 24. Troubleshooting (`panels_troubleshoot.py`)
**Description:** Diagnostics, GDB debugger, debug logs.

**Features:**
- System diagnostics
- QEMU process inspection
- GDB attachment
- Debug log viewer

---

### 4.9 Chat & AI Integration

#### 25. Chat (`panels_chat.py`)
**Description:** Built-in agentic chat panel with QEMU tool execution.

**Features:**
- Natural language VM control
- Tool execution display (expandable widgets)
- Provider selection dropdown
- Chat history
- Clear chat button

**Tool Execution Display:**
- Tool name with icon
- Arguments summary
- Result display (truncated to 500 chars)
- Success/failure indicator

---

#### 26. API Providers (`panels_providers.py`)
**Description:** AI API provider configuration management.

**Features:**
- Add/edit/remove API providers
- API key management
- Provider enable/disable
- Test connection

---

#### 27. Multi-VM Dashboard (`panels_multi_vm_dashboard.py`)
**Description:** Overview of all managed VMs.

**Features:**
- List of all VMs
- Per-VM status summary
- Quick actions for each VM
- Resource aggregation

---

## 6. API Provider Configuration

### Supported Providers

VM-Harness supports multiple AI API providers:

| Provider | API Key Variable | Base URL |
|----------|------------------|----------|
| **OpenRouter** | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` |
| **OpenAI** | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| **Google** | `GOOGLE_API_KEY` | `https://generativelanguage.googleapis.com/v1` |

### Configuration Steps

#### OpenRouter

1. Get an API key from [openrouter.ai](https://openrouter.ai)
2. In the **API Providers** panel, add a new provider:
   - Name: `OpenRouter`
   - API Key: Your OpenRouter key
   - Base URL: `https://openrouter.ai/api/v1`
3. Enable the provider

#### Anthropic

1. Get an API key from [anthropic.com](https://anthropic.com)
2. In the **API Providers** panel:
   - Name: `Anthropic`
   - API Key: Your Anthropic key
   - Base URL: `https://api.anthropic.com/v1`
3. Enable the provider

#### OpenAI

1. Get an API key from [platform.openai.com](https://platform.openai.com)
2. In the **API Providers** panel:
   - Name: `OpenAI`
   - API Key: Your OpenAI key
   - Base URL: `https://api.openai.com/v1`
3. Enable the provider

#### Google (Gemini)

1. Get an API key from [makersuite.google.com](https://makersuite.google.com)
2. In the **API Providers** panel:
   - Name: `Google`
   - API Key: Your Google API key
   - Base URL: `https://generativelanguage.googleapis.com/v1`
3. Enable the provider

### Managing Providers

| Action | How To |
|--------|--------|
| **Add Provider** | Click "Add Provider" in the API Providers panel; fill in name, base URL, model name, and API key (optional) |
| **Edit Provider** | Select a provider and click Edit; modify settings and save |
| **Delete Provider** | Select a provider and click Delete; confirm deletion |
| **Enable/Disable** | Toggle the enabled state column; disabled providers won't be used by the chat engine |
| **Test Connection** | Use the Test button to verify API connectivity; shows success/failure message |
| **Set API Key** | Click "Set API Key" to securely enter or update a provider's API key via password dialog |
| **Reorder Priority** | Use the priority column to control which provider the chat engine tries first |

### Provider Configuration via .env

Providers can also be configured via environment variables in `.env`:

```env
# API Provider Configuration
OPENROUTER_API_KEY=sk-or-v1-xxxx
ANTHROPIC_API_KEY=sk-ant-api03-xxxx
OPENAI_API_KEY=sk-xxxx
GOOGLE_API_KEY=AIzaSyxxxx
```

The chat engine reads from both the UI configuration and environment variables, with UI configuration taking precedence.

---

## 7. Multi-VM Management

### Overview

VM-Harness supports managing multiple VM instances from a single interface. Each VM has its own configuration, disk image, and resource allocation. The **VM Switcher** panel (sidebar icon: 🔄) is the central hub for multi-VM operations.

### Supported Multi-VM Features

| Feature | Description |
|---------|-------------|
| Multiple VM configs | Register any number of VM profiles with different disk images |
| Per-VM resource limits | Each VM can have its own Max RAM, Max vCPUs, and Priority |
| Independent lifecycle | Start/stop/reset/suspend/resume each VM independently |
| Per-VM snapshots | Each VM maintains its own snapshot list |
| Per-VM ISO mounting | Different ISOs can be mounted per VM |
| VM switching | Seamlessly switch the active VM target for all other panels |

### Adding a VM

**Using VM Switcher Panel:**

1. Open the **VM Switcher** panel from the sidebar
2. Click **Add VM** button
3. In the dialog, configure:
   - **VM Name:** A unique identifier for this VM (e.g., "dev-environment", "testing-vm")
   - **Disk Path:** Browse to select an existing qcow2 disk image, or enter a path to create a new one
   - **ISO Path (optional):** If installing from ISO, select the installation media
   - **RAM Allocation:** Memory in MB for this VM
   - **CPU Count:** Number of vCPUs for this VM
   - **Display Settings:** Display type (SDL, VNC, etc.)
4. Click **OK** to register the VM

The VM now appears in the VM list with a ○ (stopped) status indicator.

**Using Command Line:**

```bash
# The VM Switcher manages configurations; individual VMs are started via the Dashboard
qemu-mcp vm list  # List all registered VMs
```

### Switching Between VMs

1. In the **VM Switcher** panel, select the VM you want to control from the list
2. Click **Switch To** (or double-click the VM entry)
3. The Dashboard, VM Control, Guest Terminal, and other panels now target the selected VM
4. The active VM indicator updates throughout the UI

**Note:** Only one VM can be the "active" target at a time. Switching VMs updates all dependent panels.

### VM Status Indicators

| Indicator | Meaning |
|-----------|---------|
| ● (green) | VM is running |
| ○ (gray) | VM is stopped |
| ◐ (yellow) | VM is paused/suspended |
| ⚠ (red) | Error state |

### VM Operations Per VM

Each registered VM can be independently controlled:

| Operation | Method | Notes |
|-----------|--------|-------|
| **Start** | VM Switcher > Start, or Dashboard > ▶ Start | Requires QMP connection |
| **Stop** | VM Switcher > Stop, or Dashboard > ■ Stop | Graceful ACPI shutdown |
| **Reset** | VM Control panel > Reset button | Warm reboot via QMP `system_reset` |
| **Suspend** | VM Control panel > Suspend | Saves state to disk |
| **Resume** | VM Control panel > Resume | Restores from suspended state |
| **Create Snapshot** | Snapshots panel > Create | Per-VM snapshots |
| **Restore Snapshot** | Snapshots panel > Restore | Reverts to snapshot state |
| **Mount ISO** | VM Control panel > Eject/change ISO | Per-VM CD-ROM |

### Resource Limits Per VM

In the **VM Switcher** panel, you can set resource limits for each VM:

| Limit | Range | Description |
|-------|-------|-------------|
| **Max RAM (MB)** | 512 - GLOBAL_MAX_RAM_MB | Maximum memory this VM can allocate |
| **Max vCPUs** | 1 - GLOBAL_MAX_CPUS | Maximum CPU cores this VM can use |
| **Priority** | 1 (highest) - 10 (lowest) | Scheduling priority when multiple VMs compete for resources |

To apply limits:
1. Select the VM in VM Switcher
2. Adjust the Max RAM, Max vCPUs, and Priority spinboxes
3. Click **Apply Limits**

### Cloning a VM

1. Select the source VM in the **VM Switcher** panel
2. Click **Clone**
3. In the Clone Dialog:
   - Enter a new VM name
   - Specify the destination disk path
   - Optionally adjust resources
4. Click **Clone**

The disk image is copied using `qemu-img convert`. The new VM has the same configuration but a separate disk.

### VM Templates

Templates allow you to save VM configurations for quick reuse:

1. Click **Templates** in the VM Switcher panel
2. In the Template Manager:
   - **Save as Template:** Save the current VM's configuration as a reusable template
   - **Create from Template:** Create a new VM using a saved template
3. Templates store: VM name pattern, disk size, RAM, CPUs, display settings, and network config

### Multi-VM Dashboard

The **Multi-VM Dashboard** (if available as a separate panel) provides a consolidated view:

- **Status Grid:** All VMs listed with status indicators
- **Resource Summary:** Aggregate RAM and CPU usage across all running VMs
- **Quick Actions:** Start/stop buttons for each VM
- **Activity Log:** Consolidated log of actions across all VMs

### Best Practices for Multi-VM

1. **Name VMs descriptively:** Use names that indicate purpose (e.g., "webserver-test", "database-vm")
2. **Set appropriate resource limits:** Prevent one VM from consuming all host resources
3. **Use templates for similar VMs:** Save time when creating multiple VMs with similar configs
4. **Monitor aggregate usage:** Keep an eye on total RAM/CPU usage across all VMs
5. **Snapshot before major changes:** Create snapshots per-VM before making configuration changes

---

## 8. Snapshot Scheduling

### Overview

Snapshot scheduling allows automated creation of VM snapshots at defined intervals.

### Configuration

Access snapshot scheduling in **Settings > Snapshots** tab.

### Schedule Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Enabled | Turn scheduling on/off | Off |
| Interval (minutes) | Time between snapshots | 60 |
| Retention (count) | Max snapshots to keep | 10 |
| Snapshot name prefix | Prefix for auto-generated names | `auto-` |
| Disk path | Target disk image | From VM config |

### Creating a Schedule

1. Navigate to **Settings > Snapshots**
2. Configure the schedule parameters
3. Click **Save**
4. The scheduler runs in the background

### Manual Snapshots

You can also create snapshots manually:
- **Snapshots panel:** Click "Create", enter a name
- **CLI:** `qemu-mcp snapshot create <name>`
- **Chat:** "Create a snapshot called <name>"

### Restoring Snapshots

1. Open the **Snapshots** panel
2. Select the snapshot to restore
3. Click **Restore**
4. Confirm the action (current state will be lost)

### Deleting Snapshots

1. Select the snapshot
2. Click **Delete**
3. Confirm deletion (cannot be undone)

---

## 9. Network Configuration

### Virtual Networks

VM-Harness supports three types of virtual networks:

| Type | Description | Use Case |
|------|-------------|----------|
| **NAT** | VM shares host IP, outbound only | Default, internet access |
| **Bridged** | VM gets its own IP on host network | Server access, host communication |
| **Isolated** | VM-only network, no external access | Testing, security |

### Creating a Network

1. Open **Network** panel
2. Go to **Virtual Networks** tab
3. Click **Add Network**
4. Enter network name
5. Select network type (NAT/Bridged/Isolated)
6. Configure subnet and gateway (if applicable)

### Port Forwarding

Port forwarding maps a host port to a guest port.

**Example: SSH access**
- Host Port: `2222`
- Guest Port: `22`
- Protocol: `TCP`

This allows you to SSH into the guest at `127.0.0.1:2222`.

**Adding a Port Forward:**
1. Go to **Port Forwarding** tab
2. Click **Add Rule**
3. Specify:
   - VM name
   - Protocol (TCP/UDP)
   - Host port
   - Guest port
4. Click OK

### Firewall Rules

Firewall rules control traffic flow.

**Rule Structure:**
- Chain (input/output/forward)
- Source address
- Destination address
- Port
- Action (accept/reject/drop)
- Enabled/disabled

---

## 10. USB Passthrough

### Overview

USB passthrough allows attaching host USB devices to a running VM.

### Requirements

- QMP connection to the running VM
- Host USB device enumeration (WMI on Windows)
- QMP `device_add`/`device_del` support

### USB Device Panel

1. Open **USB/Devices** panel
2. Go to **USB Devices** tab

**Features:**
- **Device List:** Table showing all detected USB devices
- **Search/Filter:** Filter by vendor, product, serial, bus, device
- **Refresh:** Re-enumerate devices

### Attaching a USB Device

1. Select a USB device from the list
2. Click **Attach to VM**
3. The device is attached via QMP `device_add`

**QMP Command Generated:**
```json
{
  "execute": "device_add",
  "arguments": {
    "driver": "usb-host",
    "vendorid": 0x046D,
    "productid": 0xC52B,
    "bus": "usb.0",
    "id": "usb-host-046d-c52b"
  }
}
```

### Detaching a USB Device

1. Select the attached device
2. Click **Detach**
3. The device is removed via QMP `device_del`

### Auto-Attach on VM Start

1. Select a device
2. Check **Auto-attach on VM start**
3. The device will be automatically attached when the VM starts

Configuration is persisted in `~/.qemu-mcp/usb_config.json`.

### PCI Passthrough

The **PCI Passthrough** tab allows passing through PCI devices:

- **GPU:** NVIDIA RTX 3080, Intel HD Graphics
- **Storage:** NVMe SSDs
- **Other:** USB controllers, network cards

### TPM 2.0 & Secure Boot

The **TPM/Secure Boot** tab configures:
- **vTPM 2.0:** Required for Windows 11 guests
- **UEFI Secure Boot:** Verify boot chain integrity

---

## 11. Audit Logging & Security

### Security Panel Overview

The **Security** panel (sidebar icon: 🔒) provides a centralized encrypted credential vault for managing sensitive information used by VM-Harness. All credentials are protected using Fernet symmetric encryption from the `cryptography` library.

**Panel Layout:**
- **Stats Bar:** Shows total credential count and breakdown by type
- **Split View:** Credential list (left, 3/4 width) + Detail panel (right, 1/4 width)
- **Action Bar:** Add Credential button, Search input, Clear All button

### Credential Types

| Type | Icon/Color | Description | Use Cases |
|------|------------|-------------|-----------|
| `password` | Orange | Generic passwords | VM passwords, service account passwords, database credentials |
| `ssh_key` | Purple | SSH private keys | Guest SSH authentication, secure shell access |
| `api_key` | Green | API keys | AI provider keys (OpenAI, Anthropic, OpenRouter, Google), REST API keys |
| `qmp_pass` | Blue | QMP connection passwords | QMP authentication for secure QMP connections |
| `other` | Gray | Other secret types | Any custom secret not fitting the above categories |

### Adding a Credential

1. Click the **＋ Add Credential** button in the Security panel
2. The **Credential Dialog** opens with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| **Name** | Text | Yes | A descriptive identifier (e.g., "OpenAI API Key", "SSH Key for Guest") |
| **Type** | Dropdown | Yes | Select from: password, ssh_key, api_key, qmp_pass, other |
| **Secret Value** | Password field | Yes | The actual secret value (masked as you type) |
| **Description** | Text (optional) | No | Additional notes or context (e.g., "Used for GPT-4 API calls") |

3. Click **Save** to store the credential

**Encryption Process:**
- The secret value is encrypted using Fernet symmetric encryption before storage
- Encrypted values are stored in `~/.local/share/vmharness/credentials.json`
- The encryption key is derived from the system environment
- Plaintext values are never written to disk

### Viewing Credentials

**Credential List (Left Panel):**
- Displays all credentials in a QTreeWidget
- Columns: Name, Type, Description, Updated (timestamp)
- Type column is color-coded for quick visual identification
- Double-click a credential to view details in the right panel

**Credential Details (Right Panel):**
| Field | Display |
|-------|---------|
| **Name** | Bold text, the credential identifier |
| **Type** | The credential type (password, ssh_key, etc.) |
| **Description** | Optional description text |
| **Updated** | Timestamp of last modification |
| **Value** | Masked display: first 2 chars + "***" + last 2 chars |
| **Actions** | Edit button, Delete button, Copy Value (masked) button |

**Viewing Plaintext:**
- Click **Edit** to open the edit dialog
- You'll be prompted to confirm you want to view the plaintext
- The full value is shown in the dialog (with confirmation step for security)

### Editing a Credential

1. Select the credential in the list
2. Click **Edit** in the detail panel
3. The Credential Dialog opens pre-filled with current values
4. If viewing an existing secret, you'll be prompted: "Show current value?"
5. Modify fields as needed
6. Click **Save** to update

### Deleting a Credential

1. Select the credential in the list
2. Click **Delete** in the detail panel
3. Confirm the deletion in the confirmation dialog
4. The credential is permanently removed from the vault

### Searching and Filtering

- Use the **Search** input in the action bar to filter credentials by name or description
- Search is case-insensitive and matches partial strings
- The credential list updates in real-time as you type

### Clear All Credentials

- Click **Clear All** to remove all credentials from the vault
- A confirmation dialog warns: "Remove all credentials? This cannot be undone."
- Use with caution — this permanently deletes all stored secrets

### Security Best Practices

1. **Use the credential vault for all secrets:** Never hardcode passwords or API keys in configuration files
2. **Never share credentials via chat or logs:** The chat panel and log viewers should never display plaintext secrets
3. **Rotate API keys periodically:** Update API keys in the vault every 90 days or as per your security policy
4. **Delete unused credentials:** Remove credentials for services or keys that are no longer in use
5. **Enable authentication for the REST API/MCP server:** In Settings > Auth, enable API key or JWT authentication
6. **Use SSH keys instead of passwords:** Where possible, prefer SSH key authentication over password authentication
7. **Limit credential access:** Only store credentials that are needed for your current workflow

### Authentication Configuration

**Settings > Auth Tab:**

| Setting | Options | Description |
|---------|---------|-------------|
| **Auth Method** | `api_key`, `jwt`, `none` | Controls how clients authenticate to the REST API and MCP server |
| **API Key** | Stored in Security panel | The secret key clients must present |

**When authentication is enabled:**
- All API requests must include `Authorization: Bearer <token>` header
- MCP server connections require authentication
- Unauthenticated requests are rejected with HTTP 401

**Auth Method Details:**

| Method | Description | Use Case |
|--------|-------------|----------|
| `none` | No authentication required | Development only; never use in production |
| `api_key` | Simple API key in Authorization header | Quick setup, single-user deployments |
| `jwt` | JSON Web Token validation | Multi-user, production deployments with token expiry |

### Credential Storage Location

Credentials are stored in:
```
~/.local/share/vmharness/credentials.json
```

**File permissions:** The file is created with restricted permissions (0o600) to prevent unauthorized access.

### Encryption Details

- **Algorithm:** Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
- **Key derivation:** Key is derived from system-specific entropy
- **Storage:** Encrypted values are base64-encoded JSON
- **Security:** Even if the credentials file is stolen, decryption requires the system-specific key

---

## 12. Troubleshooting

This section covers common issues and their solutions. For additional help, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and the Troubleshoot panel in the application.

### 12.1 QEMU Not Found

**Symptom:** Error message "QEMU binary not found" or QEMU fails to start.

**Diagnostic Steps:**

1. Verify QEMU is installed:
   ```bash
   qemu-system-x86_64 --version
   ```
   If this command fails, QEMU is not installed or not in your PATH.

2. Check the QEMU binary path in Settings:
   - Go to **Settings > QEMU** tab
   - Verify the "QEMU Binary" field shows the correct path
   - Click **Refresh from .env** to reload settings from file

3. Common Windows QEMU paths:
   ```
   C:/Program Files/qemu/qemu-system-x86_64.exe
   C:/qemu/qemu-system-x86_64.exe
   C:/Users/<username>/qemu/qemu-system-x86_64.exe
   ```

**Solutions:**

| Solution | Steps |
|----------|-------|
| **Install QEMU** | Download from [qemu.org](https://www.qemu.org/download/). On Windows, use the Windows installer or extract pre-built binaries to a known location. |
| **Fix path in Settings** | Go to Settings > QEMU tab, update the QEMU Binary field, click Save Settings, restart the application. |
| **Add QEMU to PATH** | Add QEMU's directory to your system PATH environment variable. Then restart your terminal/IDE. |
| **Verify file exists** | Use File Explorer or `test-path` in PowerShell to confirm the QEMU executable exists at the configured path. |

---

### 12.2 SSH Failures

**Symptom:** Guest terminal/agent cannot connect; "Connection refused" or timeout errors.

**Diagnostic Steps:**

1. Verify the VM is running (check Dashboard status indicator)
2. Check SSH port forwarding is configured:
   - Default: host port 2222 → guest port 22
   - Verify in **Settings > Network** tab
3. Ensure SSH server is running inside the guest:
   - Linux: `sudo systemctl status sshd` or `sudo service ssh status`
   - Check listening ports: `sudo ss -tlnp | grep :22`
4. Verify SSH credentials:
   - Username: default is `omarchyvm`
   - Password or private key must be correct

**Solutions:**

| Issue | Solution |
|-------|----------|
| **SSH server not installed** | Install openssh-server in the guest: `sudo apt install openssh-server` (Debian/Ubuntu) or `sudo yum install openssh-server` (RHEL/CentOS) |
| **SSH server not running** | Start the service: `sudo systemctl start sshd` |
| **Wrong port** | Check that host port 2222 is correctly forwarded to guest port 22. Verify in Network > Port Forwarding tab. |
| **Authentication failed** | Verify username/password or SSH private key path in Settings > Network tab. Try using SSH key instead of password. |
| **Port conflict on host** | Another application is using port 2222. Select a different host port in Settings. |
| **Firewall blocking** | Check Windows Firewall or host firewall allows connections on the SSH port. |

**Note:** If there's no SSH server in the guest VM, you'll need to install one. Use any available method: console access, cloud-init, or mounting the disk on the host.

---

### 12.3 QMP Failures

**Symptom:** VM control operations fail; "QMP disconnected" or "QMP command failed" errors.

**Diagnostic Steps:**

1. Verify QMP settings:
   - Check **Settings > Network** tab or `.env` file:
     ```
     QMP_HOST=127.0.0.1
     QMP_PORT=4444
     ```
2. Ensure QMP socket is accessible:
   - QEMU must be started with `-qmp tcp:127.0.0.1:4444,server,nowait`
   - This is typically handled automatically by VM-Harness
3. Check if QEMU process is running:
   ```bash
   tasklist | findstr qemu   # Windows
   ps aux | grep qemu        # Linux
   ```
4. Verify the QMP port is not blocked by firewall

**Solutions:**

| Issue | Solution |
|-------|----------|
| **QMP port in use** | Another application is using port 4444. Change QMP_PORT in Settings to a different port. |
| **QEMU not started with QMP** | VM-Harness adds QMP args automatically. If starting QEMU manually, include `-qmp tcp:127.0.0.1:4444,server,nowait`. |
| **Connection timeout** | Check firewall rules. Ensure QEMU process is actually running. |
| **QMP commands failing** | Verify the VM is in a state that accepts the command (e.g., can't start an already-running VM). |
| **QMP authentication failed** | If QMP password is set, ensure it matches in Settings. |

---

### 12.4 VM Won't Start

**Symptoms:** Clicking Start has no effect, or error message appears.

**Diagnostic Steps & Solutions:**

| Check | How To | Solution |
|-------|--------|----------|
| **Disk image exists** | Check path in Settings > VM tab. Verify file exists. | Create or correct the disk path. Use Storage panel to create a new disk if needed. |
| **Disk image valid** | Run: `qemu-img check <disk-path>` | If corrupt, restore from snapshot or create new disk. |
| **RAM/CPU values valid** | Check Settings > VM tab. RAM: 256-131072 MB, CPUs: 1-128. | Adjust values to be within valid ranges. |
| **Port conflicts** | Check if ports 2222 (SSH) and 4444 (QMP) are available. | Change ports in Settings if conflicts exist. |
| **Another VM using resources** | Check VM Switcher for other running VMs. | Stop other VMs or reduce resource allocations. |
| **Insufficient host resources** | Check host RAM and CPU availability. | Reduce VM RAM/CPU or close other applications. |
| **Acceleration mode issue** | WHPX may not be enabled. Check Windows Features. | Enable Windows Hypervisor Platform or switch to TCG (slower). |

---

### 12.5 Display Issues

**Symptom:** No display window appears, or display is blank.

**Solutions by Display Type:**

| Display Type | Issue | Solution |
|--------------|-------|----------|
| **SDL** | Window doesn't appear | Ensure SDL library is installed. Check if VM actually started. Try switching to VNC. |
| **VNC** | Can't connect via VNC client | Connect to `127.0.0.1:5900` (or configured port). Verify VNC port is not blocked. |
| **GTK** | Window doesn't appear | Ensure GTK libraries are available. Try switching to SDL. |
| **SPICE** | Can't connect | Install SPICE client (virt-viewer, spicy). Connect to configured SPICE port (default 5930). |
| **None** | Expected behavior | VM runs headless. Use SSH or VNC to access the guest. |
| **Any** | VM started but no display | Check if guest OS has graphical desktop installed. Some server OS installations have no GUI. |

---

### 12.6 Acceleration Problems

**Symptom:** VM is very slow, or acceleration warning appears.

**Acceleration Modes:**

| Mode | Description | Performance | When to Use |
|------|-------------|-------------|--------------|
| **WHPX** | Windows Hypervisor Platform | Best on Windows | Default for Windows 10/11 |
| **HAXM** | Intel Hardware Accelerator | Good | Intel VT-x systems with HAXM installed |
| **TCG** | Software emulation | Very slow (10-100x) | Fallback when hardware acceleration unavailable |

**Solutions:**

| Issue | Solution |
|-------|----------|
| **WHPX not working** | Enable "Windows Hypervisor Platform" in Windows Features. Run PowerShell as Administrator: `Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform`. Restart computer. |
| **HAXM not working** | Install Intel HAXM driver. Ensure Intel VT-x is enabled in BIOS/UEFI. |
| **TCG too slow** | This is expected. TCG is software emulation without hardware acceleration. Use WHPX or HAXM if available. |
| **Acceleration warning shown** | The warning appears when TCG is selected. Switch to WHPX or HAXM in Settings > Acceleration tab. |
| **VT-x/AMD-V disabled in BIOS** | Enter BIOS/UEFI setup and enable virtualization technology (Intel VT-x or AMD-V). |

---

### 12.7 Network Issues

**Symptom:** VM cannot access network, port forwarding doesn't work.

**Solutions:**

| Issue | Solution |
|-------|----------|
| **No internet in VM** | Verify NAT networking is configured. Check host has internet. Try bridged networking. |
| **Port forwarding not working** | 1. Verify VM is running. 2. Check port forward rule is correct. 3. Ensure host port is not blocked by firewall. 4. Test with `telnet 127.0.0.1 <host-port>`. |
| **Cannot reach VM** | For SSH: `ssh -p <port> user@127.0.0.1`. For VNC: connect to `127.0.0.1:<port>`. For bridged: use VM's actual IP on network. |
| **SSH connection refused** | SSH server not running in guest. Install and start openssh-server. |
| **Firewall blocking** | Check host firewall (Windows Defender Firewall, iptables, etc.) allows traffic on relevant ports. |

---

### 12.8 Snapshot Errors

**Symptom:** Snapshot creation/restore/delete fails.

**Solutions:**

| Issue | Solution |
|-------|----------|
| **Snapshot creation fails** | 1. Verify `qemu-img` is installed and in PATH. 2. Check disk path is correct and writable. 3. Pause VM first for data consistency. |
| **Snapshot list empty** | Click Refresh in Snapshots panel. Verify disk path is correct. |
| **Restore fails** | 1. Stop VM before restoring. 2. Ensure write access to disk image. 3. Verify snapshot name is correct. |
| **Delete fails** | Ensure VM is not running. Check write permissions on disk image. |

---

### 12.9 GUI Problems

**Symptom:** GUI doesn't start, crashes, or panels don't load.

**Solutions:**

| Issue | Solution |
|-------|----------|
| **GUI won't start** | 1. Check Python and PyQt5: `python -c "import PyQt5; print(PyQt5.__version__)"`. 2. Run with debug: `qemu-mcp gui --debug`. 3. Check terminal for error messages. |
| **GUI crashes** | 1. Check crash logs. 2. Verify VM-Harness version is compatible. 3. Try running from source: `python -m gui`. |
| **Panels don't load** | 1. Restart application. 2. Check for error messages. 3. Verify all dependencies installed. |
| **UI unresponsive** | Check if QEMU process is hanging. Check available system resources. |
| **Display glitchy** | Try different display backend in Settings. Update graphics drivers. |

---

### 12.10 Performance Issues

**Symptom:** VM runs slowly, high host CPU usage, guest responds slowly.

**Optimization Steps:**

1. **Use hardware acceleration:** Enable WHPX or HAXM in Settings > Acceleration
2. **Allocate adequate RAM:** Minimum 2 GB for modern OS; more for heavyweight workloads
3. **Use qcow2 disk format:** Better performance than raw for most use cases
4. **Enable OpenGL:** If available, enables graphics acceleration
5. **Reduce vCPU count:** If host is overloaded, reduce VM CPUs
6. **Monitor resource usage:** Use Telemetry and Monitoring panels to identify bottlenecks

**Check Resource Usage:**
- Use **Telemetry** panel for real-time charts
- Use **Monitoring** panel for historical data
- Check host Task Manager/Activity Monitor for host resource usage

---

### 12.11 Debugging Tips

**Enable Debug Logging:**
```
# In Settings > Logging tab, or .env:
LOG_LEVEL=DEBUG
LOG_FILE=debug.log
```

**Check QEMU Command Line:**
VM-Harness shows the QEMU command it would execute. You can also run QEMU manually:
```bash
qemu-system-x86_64 -machine q35 -m 8192 -smp 4 \
  -drive file=disk.qcow2,format=qcow2 \
  -display sdl -qmp tcp:127.0.0.1:4444,server,nowait
```

**Use QMP Console:**
Send manual QMP commands in the QMP Console panel:
```json
{"execute": "query-status"}
{"execute": "query-commands"}
{"execute": "query-version"}
```

**Collect Diagnostic Information for Bug Reports:**
1. VM-Harness version (from `gui/__main__.py` or `pyproject.toml`)
2. Python version: `python --version`
3. QEMU version: `qemu-system-x86_64 --version`
4. Operating system and version
5. Relevant error messages (from Logs panel)
6. QEMU command line being used
7. `.env` settings (remove sensitive values before sharing)

## 13. Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + Q` | Quit application | Anywhere |
| `Ctrl + S` | Save settings (in Settings panel) | Settings panel |
| `Ctrl + R` | Refresh current view | Any panel |
| `Ctrl + F` | Search (in applicable panels) | Logs, Security, ISO, Network panels |
| `Ctrl + P` | Toggle sidebar visibility | Anywhere |
| `F11` | Toggle fullscreen mode | Anywhere |
| `Alt + F4` | Close window | Anywhere |

### Chat Panel Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Enter` | Send message | Chat input focused |
| `Ctrl + L` | Clear chat history | Chat panel |
| `Ctrl + Shift + C` | Copy last AI response | Chat panel |
| `Up Arrow` | Scroll up in chat history | Chat display focused |
| `Down Arrow` | Scroll down in chat history | Chat display focused |

### VM Control Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `F5` | Refresh VM status | Dashboard, VM Control panels |
| `Space` | Start/Stop VM (toggle) | Dashboard, when status card focused |
| `Ctrl + Shift + S` | Start VM | Any VM panel |
| `Ctrl + Shift + X` | Stop VM | Any VM panel |
| `Ctrl + Shift + R` | Reset VM | Any VM panel |
| `Ctrl + Shift + P` | Suspend VM | Any VM panel |
| `Ctrl + Shift + E` | Resume VM | Any VM panel |
| `Ctrl + Shift + I` | Eject ISO | VM Control panel |

### Navigation Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + Tab` | Next panel/tab | Anywhere |
| `Ctrl + Shift + Tab` | Previous panel/tab | Anywhere |
| `Ctrl + 1` through `Ctrl + 9` | Jump to sidebar panel N | Anywhere |
| `Alt + Left Arrow` | Navigate back | Anywhere |
| `Alt + Right Arrow` | Navigate forward | Anywhere |
| `Ctrl + G` | Go to line (in logs/code views) | Log viewers, text displays |

### Text Editing Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + C` | Copy | Text selection |
| `Ctrl + V` | Paste | Text input focused |
| `Ctrl + X` | Cut | Text selection |
| `Ctrl + A` | Select all | Text area focused |
| `Ctrl + Z` | Undo | Text input focused |
| `Ctrl + Y` | Redo | Text input focused |

### Settings Panel Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + S` | Save settings | Settings panel |
| `Ctrl + Shift + R` | Reset to defaults | Settings panel |
| `Ctrl + Shift + L` | Load from .env file | Settings panel |

### Accessibility Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + +` (plus) | Increase font size | Text panels |
| `Ctrl + -` (minus) | Decrease font size | Text panels |
| `Ctrl + 0` | Reset font size to default | Text panels |

### Power User Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl + Shift + D` | Open debug console | Anywhere |
| `F12` | Open developer tools | Anywhere |

## 14. Configuration Reference

VM-Harness stores all configuration in a `.env` file (or an alternate location specified by `VM_MCP_ENV_FILE`). This reference documents every configuration variable, its purpose, default value, and valid ranges.

### Configuration File Location

| Platform | Default Location |
|----------|------------------|
| Windows | `%USERPROFILE%\.qemu-mcp\.env` or project root `.env` |
| Linux | `~/.config/qemu-mcp/.env` or project root `.env` |
| macOS | `~/Library/Application Support/qemu-mcp/.env` or project root `.env` |

**Override:** Set the `VM_MCP_ENV_FILE` environment variable to use a custom location.

### Complete Variable Reference

#### QEMU Binary Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `QEMU_BINARY` | string | `qemu-system-x86_64` | Path to QEMU executable | Any valid path |
| `QEMU_EXTRA_ARGS` | string | `-machine q35,kernel_platform=` | Additional QEMU arguments | Any valid QEMU args |

**Example:**
```env
QEMU_BINARY="C:/Program Files/qemu/qemu-system-x86_64.exe"
QEMU_EXTRA_ARGS="-machine q35,kernel_platform= -cpu host"
```

#### Virtual Machine Settings

| Variable | Type | Default | Description | Valid Range |
|----------|------|---------|-------------|-------------|
| `VM_NAME` | string | `omarchy-vm` | VM identifier | Any non-empty string |
| `VM_DISK` | string | (none) | Path to qcow2 disk image | Must exist or be creatable |
| `VM_ISO` | string | (none) | Path to installation ISO | Must exist if set |
| `VM_RAM_MB` | integer | `8192` | VM RAM in MB | 256 - 131072 (128 GB) |
| `VM_CPUS` | integer | `4` | Number of vCPUs | 1 - 128 |
| `VM_HOSTNAME` | string | `omarchy-vm` | Guest OS hostname | Any valid hostname |
| `VM_ADDTL_OPTS` | string | (none) | Additional VM options | Any valid QEMU opts |

**Example:**
```env
VM_NAME="desktop-vm"
VM_DISK="C:/Users/Server/Virtual Machines/desktop-vm/disk.qcow2"
VM_RAM_MB="16384"
VM_CPUS="8"
```

#### Display Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `DISPLAY` | string | `sdl` | Display backend | `sdl`, `gtk`, `vnc`, `spice`, `none` |
| `OPENGL` | boolean | `1` | Enable OpenGL | `0` or `1` |
| `AUTO_EJECT_ISO` | boolean | `1` | Auto-eject ISO after boot | `0` or `1` |
| `VNC_PORT` | integer | `5900` | VNC server port | 5900 - 5999 |
| `SPICE_PORT` | integer | `5930` | SPICE server port | 5930 - 5999 |

#### Acceleration Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `VM_ACCELERATION` | string | `whpx` | Hardware acceleration | `whpx`, `haxm`, `tcg` |

| Mode | Platform | Performance | Requirements |
|------|----------|-------------|--------------|
| `whpx` | Windows | Best | Windows 10/11 with WHPX enabled |
| `haxm` | Windows/Linux | Good | Intel VT-x with HAXM driver |
| `tcg` | All | Very slow (10-100x) | None (software fallback) |

#### Network/SSH Settings

| Variable | Type | Default | Description | Valid Range |
|----------|------|---------|-------------|-------------|
| `SSH_HOST` | string | `127.0.0.1` | SSH host | Valid IP/hostname |
| `SSH_PORT` | integer | `2222` | SSH port | 1 - 65535 |
| `SSH_USERNAME` | string | `omarchyvm` | SSH username | Any valid username |
| `SSH_PASSWORD` | string | (none) | SSH password | Any string (not recommended) |
| `SSH_PRIVATE_KEY` | string | (none) | Path to SSH private key | Must exist if set |
| `SSH_TIMEOUT` | integer | `30` | Connection timeout (seconds) | 1 - 300 |

#### QMP Settings

| Variable | Type | Default | Description | Valid Range |
|----------|------|---------|-------------|-------------|
| `QMP_HOST` | string | `127.0.0.1` | QMP TCP host | Valid IP/hostname |
| `QMP_PORT` | integer | `4444` | QMP TCP port | 1 - 65535 |
| `QMP_PASS` | string | (none) | QMP password | Any string |
| `QMP_TIMEOUT` | integer | `30` | Connection timeout | 1 - 300 |

#### Logging Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `LOG_LEVEL` | string | `INFO` | Log verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE` | string | (none) | Path to log file | Any valid path |

| Level | Description | Use Case |
|-------|-------------|----------|
| `DEBUG` | Most verbose | Development, troubleshooting |
| `INFO` | Standard | Normal operation |
| `WARNING` | Warnings only | Production (minimal) |
| `ERROR` | Errors only | Production (minimal) |
| `CRITICAL` | Critical only | Production (minimal) |

#### Snapshot Scheduler Settings

| Variable | Type | Default | Description | Valid Range |
|----------|------|---------|-------------|-------------|
| `SNAPSHOT_SCHEDULE_ENABLED` | boolean | `false` | Enable auto-snapshots | `true` or `false` |
| `SNAPSHOT_INTERVAL_MINUTES` | integer | `60` | Time between snapshots | 1 - 1440 |
| `SNAPSHOT_RETENTION_COUNT` | integer | `10` | Max snapshots to keep | 1 - 100 |
| `SNAPSHOT_NAME_PREFIX` | string | `auto-` | Prefix for names | Any string |

#### Authentication Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `AUTH_ENABLED` | boolean | `false` | Enable authentication | `true` or `false` |
| `AUTH_METHOD` | string | `api_key` | Auth method | `api_key`, `jwt`, `none` |
| `API_KEY` | string | (none) | API key | Any secret string |

| Method | Description | Use Case |
|--------|-------------|----------|
| `none` | No authentication | Development only |
| `api_key` | Simple API key | Single-user, quick setup |
| `jwt` | JWT validation | Multi-user, production |

#### Transport/MCP Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `TRANSPORT` | string | `stdio` | MCP transport | `stdio`, `sse` |
| `SSE_HOST` | string | `127.0.0.1` | SSE server host | Valid IP/hostname |
| `SSE_PORT` | integer | `8080` | SSE server port | 1 - 65535 |

### Settings Panel GUI Mapping

The Settings panel provides a GUI editor. Each tab corresponds to a group:

| Tab | Variables |
|-----|-----------|
| **QEMU** | `QEMU_BINARY`, `QEMU_EXTRA_ARGS` |
| **VM** | `VM_NAME`, `VM_DISK`, `VM_ISO`, `VM_RAM_MB`, `VM_CPUS`, `VM_HOSTNAME` |
| **Display** | `DISPLAY`, `OPENGL`, `AUTO_EJECT_ISO` |
| **Acceleration** | `VM_ACCELERATION` |
| **Network** | `SSH_HOST`, `SSH_PORT`, `SSH_USERNAME`, `SSH_PRIVATE_KEY` |
| **Logging** | `LOG_LEVEL`, `LOG_FILE` |
| **Snapshots** | `SNAPSHOT_SCHEDULE_ENABLED`, `SNAPSHOT_INTERVAL_MINUTES`, `SNAPSHOT_RETENTION_COUNT`, `SNAPSHOT_NAME_PREFIX` |
| **Auth** | `AUTH_ENABLED`, `AUTH_METHOD`, `API_KEY` |

### Validation Rules

| Setting | Validation | Error if Invalid |
|---------|------------|------------------|
| `QEMU_BINARY` | File must exist | "QEMU binary not found" |
| `VM_DISK` | File must exist (if provided) | "Disk image not found" |
| `SSH_PORT` | 1 - 65535 | "SSH port out of range" |
| `QMP_PORT` | 1 - 65535 | "QMP port out of range" |
| `VM_RAM_MB` | 256 - 131072 | "RAM out of range (256-131072 MB)" |
| `VM_CPUS` | 1 - 128 | "CPUs out of range (1-128)" |
| `SSH_PRIVATE_KEY` | File must exist (if provided) | "SSH key file not found" |

### Configuration Best Practices

1. **Use the Settings panel** rather than editing `.env` directly — it validates inputs
2. **Back up your `.env`** before making major changes
3. **Use SSH keys** instead of passwords (`SSH_PRIVATE_KEY` over `SSH_PASSWORD`)
4. **Store secrets in the credential vault** (Security panel), not in `.env`
5. **Enable debug logging** (`LOG_LEVEL=DEBUG`) when troubleshooting
6. **Create a snapshot** before changing VM resource settings
7. **Test after changes** — always verify the VM starts correctly

### Sample Complete Configuration

```env
# QEMU Configuration
QEMU_BINARY="C:/Program Files/qemu/qemu-system-x86_64.exe"
QEMU_EXTRA_ARGS="-machine q35,kernel_platform="

# VM Configuration
VM_NAME="omarchy-vm"
VM_DISK="C:/Users/Server/Virtual Machines/omarchy-vm/disk.qcow2"
VM_ISO=""
VM_RAM_MB="16384"
VM_CPUS="8"
VM_HOSTNAME="omarchy-vm"

# Display
DISPLAY="sdl"
OPENGL="1"
AUTO_EJECT_ISO="1"

# Acceleration
VM_ACCELERATION="whpx"

# Network/SSH
SSH_HOST="127.0.0.1"
SSH_PORT="2222"
SSH_USERNAME="omarchyvm"
SSH_PRIVATE_KEY=""
SSH_TIMEOUT="30"

# QMP
QMP_HOST="127.0.0.1"
QMP_PORT="4444"
QMP_TIMEOUT="30"

# Logging
LOG_LEVEL="INFO"
LOG_FILE=""

# Snapshot Scheduler
SNAPSHOT_SCHEDULE_ENABLED="false"
SNAPSHOT_INTERVAL_MINUTES="60"
SNAPSHOT_RETENTION_COUNT="10"
SNAPSHOT_NAME_PREFIX="auto-"

# Authentication
AUTH_ENABLED="false"
AUTH_METHOD="api_key"
```

## 15. FAQ

### 15.1 General Questions

**Q: What is VM-Harness?**
A: VM-Harness is a comprehensive desktop application for controlling QEMU virtual machines. It provides a dark-themed PyQt5 GUI with 25+ specialized panels, a CLI tool, a REST API, and an MCP server for AI agent integration. Key features include agentic AI chat, multi-VM management, snapshot scheduling, USB passthrough, and self-healing capabilities.

**Q: Is VM-Harness free and open source?**
A: Yes. VM-Harness is free and open-source software released under the MIT License. You can use, modify, and distribute it freely.

**Q: Who develops VM-Harness?**
A: VM-Harness is developed by Omarchy VM Control and is available on GitHub.

**Q: Which platforms are supported?**
A: VM-Harness is tested and supported on Windows 10/11 with WHPX hardware acceleration. The code is written to be cross-platform (PyQt5, Python standard library), but Linux and macOS have not been extensively tested. Users on those platforms may need to adjust paths and configurations.

**Q: What Python version do I need?**
A: Python 3.10 or later is required. Python 3.11 or 3.13 is recommended for full async feature support.

### 15.2 Installation & Setup

**Q: How do I install QEMU?**
A: Download QEMU from [qemu.org](https://www.qemu.org/download/).
- **Windows:** Use the Windows installer or extract pre-built binaries to a known location (e.g., `C:/Program Files/qemu/`)
- **Linux:** `sudo apt install qemu-system-x86` (Debian/Ubuntu) or equivalent for your distribution
- **macOS:** `brew install qemu`

**Q: How do I install VM-Harness?**
A: See the [Installation section](#2-installation) for detailed instructions. Briefly:
```bash
git clone https://github.com/your-org/qemu-mcp.git
cd qemu-mcp
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
qemu-mcp gui
```

**Q: Can I install VM-Harness without Python?**
A: Yes, if using the standalone EXE. The `dist/VM-Harness.exe` is built with PyInstaller and bundles Python, all dependencies, and the application. No Python installation is required.
To build the EXE yourself:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name VM-Harness gui/__main__.py
```

**Q: What Windows features do I need to enable?**
A: For WHPX acceleration (recommended):
1. Open PowerShell as Administrator
2. Run:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform
   Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
   ```
3. Restart your computer

**Q: How much RAM and disk space do I need?**
A: Minimum requirements:
- Host RAM: 8 GB (16 GB+ recommended)
- Disk space: 10 GB free (50 GB+ recommended for VM images)
- VM RAM: 256 MB - 128 GB (depending on guest OS requirements)
- VM disk: 1 GB - 2 TB (depending on guest needs)

### 15.3 VM Management

**Q: How do I start a VM?**
A: Three methods:
1. **GUI:** Click ▶ Start VM on the Dashboard panel
2. **CLI:** `qemu-mcp vm start <vm-name>`
3. **AI Chat:** "Start my VM"

**Q: How do I stop a VM?**
A: Three methods:
1. **GUI:** Click ■ Stop VM on the Dashboard panel
2. **CLI:** `qemu-mcp vm stop <vm-name>`
3. **AI Chat:** "Shut down the VM"
The VM receives a graceful ACPI shutdown signal. If it doesn't respond, use Reset for a forced reset.

**Q: Can I run multiple VMs at once?**
A: Yes. Use the VM Switcher panel to register and manage multiple VM configurations. Each VM can be started, stopped, and controlled independently. Only one VM is the "active" target at a time for other panels.

**Q: How do I create a new VM?**
A: Use the Create VM wizard (➕ Create VM in sidebar). The 5-step wizard guides you through:
1. Identity (name, OS type, machine type, firmware)
2. Hardware (CPUs, RAM, passthrough, I/O threads)
3. Storage (disk size, format, cache mode, ISO)
4. Network (NAT/Bridged/Isolated, port forwards)
5. Review and create

**Q: How do I increase VM RAM?**
A: In Settings > VM tab, adjust the RAM slider. Note: Memory hotplug is not supported; the VM must be restarted for RAM changes to take effect.

**Q: How do I change the CPU count?**
A: In Settings > VM tab, adjust the vCPUs spinner. Like RAM, CPU changes require a VM restart.

**Q: What hardware acceleration should I use?**
A: Use WHPX on Windows 10/11 for best performance. HAXM is an alternative for Intel systems. TCG is software emulation and is very slow (10-100x slower than hardware acceleration) — only use as a fallback.

### 15.4 Guest Access

**Q: How do I access the guest OS?**
A: Three methods:
1. **SSH Terminal:** Guest Terminal panel — SSH into the VM with command execution and file browser
2. **Guest Agent:** Guest Agent panel — Browse files, execute commands, manage processes and services
3. **Display:** VNC/SPICE display — Connect with a VNC or SPICE client for graphical access

**Q: How do I SSH into the VM?**
A: Default connection:
```
ssh -p 2222 omarchyvm@127.0.0.1
```
Requirements:
- VM must be running
- SSH server must be running in the guest (install `openssh-server` if not)
- Port forwarding configured: host 2222 → guest 22

**Q: Can I use SSH keys instead of passwords?**
A: Yes. Configure `SSH_PRIVATE_KEY` in `.env` with the path to your SSH private key. The SSH bridge will use key-based authentication. You can also store the key in the Security panel's credential vault.

**Q: Why can't I see the VM display?**
A: Depends on display type:
- **SDL/GTK:** The display window should appear automatically. If not, check that the QEMU binary supports the selected display backend.
- **VNC:** Connect to `127.0.0.1:5900` (or configured port) using a VNC client.
- **SPICE:** Connect to `127.0.0.1:5930` (or configured port) using a SPICE client (virt-viewer, spicy).
- **None:** VM runs headless; use SSH or VNC to access.
- **Guest has no GUI:** Some server OS installations don't include a graphical desktop. Use SSH for command-line access.

**Q: How do I mount an ISO?**
A: 1. Go to ISO Manager panel and import or select an ISO. 2. In VM Control panel, the ISO can be mounted via QMP. 3. Or configure `VM_ISO` in `.env`. The ISO is mounted as a virtual CD-ROM. If `AUTO_EJECT_ISO` is enabled (default), it's automatically ejected after boot.

### 15.5 Networking

**Q: Can the VM access the internet?**
A: Yes, with NAT networking (the default). The VM shares the host's IP for outbound connections. Inbound connections require port forwarding.

**Q: How do I access the VM from other devices on my network?**
A: Configure Bridged networking:
1. Go to Network > Virtual Networks tab
2. Click Add Network
3. Select Bridged type
4. The VM gets its own IP on your local network

**Q: How do I set up port forwarding?**
A: In Network > Port Forwarding tab:
1. Click Add Rule
2. Configure: VM name, Protocol (TCP/UDP), Host port, Guest port
3. Click OK
Example: Host port 8080 → Guest port 80 allows accessing a web server in the VM at `http://127.0.0.1:8080`.

**Q: What firewall rules can I configure?**
A: In Network > Firewall Rules tab, you can configure:
- Chain (input, output, forward)
- Source IP/network
- Destination IP/network
- Port or port range
- Action (accept, reject, drop)
- Enable/disable toggle

### 15.6 Snapshots

**Q: What is a snapshot?**
A: A snapshot captures the complete state of the VM's disk at a point in time using `qemu-img` on qcow2 images. You can restore the VM to that exact state later, undoing any changes made since.

**Q: How do I create a snapshot?**
A: Three methods:
1. **GUI:** Snapshots panel > Click Create > Enter a name
2. **CLI:** `qemu-mcp snapshot create <name>`
3. **AI Chat:** "Create a snapshot called <name>"

**Q: How do I restore a snapshot?**
A: 1. Open Snapshots panel. 2. Select the snapshot. 3. Click Restore. 4. Confirm. Warning: This discards all changes made since the snapshot was created.

**Q: Can I snapshot a running VM?**
A: Yes, but for data consistency, it's recommended to pause the VM first or use external snapshot tools. QEMU supports internal snapshots via `qemu-img`, which work on running VMs but may capture in-flight I/O.

**Q: Do snapshots affect performance?**
A: Creating a snapshot is fast. Having many snapshots can slightly slow disk operations. The Snapshot Scheduler can automatically manage retention (keep only the most recent N snapshots).

**Q: How does the Snapshot Scheduler work?**
A: Configure in Settings > Snapshots tab:
- Enabled: Toggle scheduling on/off
- Interval: Time between snapshots (minutes, default 60)
- Retention: Max snapshots to keep (default 10)
- Name prefix: Prefix for auto-generated names (default `auto-`)
The scheduler runs in the background and creates snapshots automatically.

### 15.7 AI Chat

**Q: How do I use the Agentic Chat?**
A: 1. Configure an API provider in the API Providers panel. 2. Go to Chat panel. 3. Select your provider. 4. Type a natural language request. The AI will execute QEMU tools automatically.

**Q: Which AI providers are supported?**
A: - **OpenRouter** (aggregates multiple models) — Get key at openrouter.ai
- **Anthropic** (Claude models) — Get key at anthropic.com
- **OpenAI** (GPT models) — Get key at platform.openai.com
- **Google** (Gemini models) — Get key at makersuite.google.com
- **Custom** — Any OpenAI-compatible API

**Q: What can the chat control?**
A: The chat can execute tools for:
- VM lifecycle: start, stop, reset, suspend, resume, status
- Guest operations: execute commands, read/write/list/remove files
- Snapshots: create, list, restore
- ISOs: list, import
- Usage: get resource usage statistics

**Q: Why did my chat request fail?**
A: Common causes:
- "No provider configured" — Set up an API key in API Providers panel
- "VM not running" — Start the VM first
- "SSH unreachable" — Install SSH server in guest and configure port forwarding
- "QMP disconnected" — Restart VM or check QMP settings
- "Tool error" — Check the error details; verify your configuration

**Q: Can I add a custom AI provider?**
A: Yes. Click "Add Custom" in the API Providers panel and enter: provider name, base URL, model name, and optional API key. The provider must be OpenAI-compatible.

### 15.8 Security & Credentials

**Q: Where are my credentials stored?**
A: In `~/.local/share/vmharness/credentials.json`, encrypted using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256). The file has restricted permissions (0o600).

**Q: What credential types are supported?**
A: - `password` — Generic passwords
- `ssh_key` — SSH private keys
- `api_key` — API keys (OpenAI, Anthropic, etc.)
- `qmp_pass` — QMP connection passwords
- `other` — Other secret types

**Q: How do I enable authentication for the API/MCP server?**
A: 1. Go to Settings > Auth tab. 2. Set Auth Method to `api_key` or `jwt`. 3. Configure the API key in the Security panel. 4. Clients must send `Authorization: Bearer <token>` on each request.

**Q: What security best practices should I follow?**
A: 1. Use the credential vault for all secrets. 2. Never share credentials via chat or logs. 3. Rotate API keys periodically (every 90 days). 4. Delete unused credentials. 5. Enable authentication for production use. 6. Use SSH keys instead of passwords. 7. Limit credential access to only what's needed.

### 15.9 USB & Hardware

**Q: How do I attach a USB device to my VM?**
A: 1. Go to USB/Devices > USB Devices tab. 2. Select a USB device from the list. 3. Click Attach to VM. The device is attached via QMP `device_add` with `usb-host` driver.

**Q: What is auto-attach?**
A: Enable "Auto-attach on VM start" to automatically reattach a USB device when the VM starts. Configuration is persisted in `~/.qemu-mcp/usb_config.json`.

**Q: Does VM-Harness support PCI passthrough?**
A: Yes, the PCI Passthrough tab allows passing through PCI devices like GPUs (NVIDIA RTX 3080, Intel HD Graphics), NVMe SSDs, USB controllers, and network cards. Requires IOMMU/VFIO setup on the host.

**Q: What is vTPM 2.0 and do I need it?**
A: vTPM 2.0 is a virtual Trusted Platform Module required for Windows 11 guests. It provides secure key storage and attestation. Configure in USB & Devices > TPM / Secure Boot tab.

### 15.10 Troubleshooting

**Q: QEMU won't start — what should I check?**
A: 1. Verify QEMU is installed: `qemu-system-x86_64 --version`. 2. Check QEMU binary path in Settings > QEMU tab. 3. Verify disk image exists. 4. Check RAM/CPU values are valid. 5. Ensure required ports (2222, 4444) are available.

**Q: SSH connection fails — what should I check?**
A: 1. Verify VM is running. 2. Check SSH server is running in guest. 3. Verify port forwarding (host 2222 → guest 22). 4. Check credentials (username, password/key). 5. Check firewall rules on host and guest.

**Q: QMP errors — what should I check?**
A: 1. Verify QMP settings (host 127.0.0.1, port 4444). 2. Ensure QEMU started with QMP enabled. 3. Check QEMU process is running. 4. Check firewall rules. 5. Restart VM if connection was lost.

**Q: VM is very slow — how do I fix it?**
A: 1. Enable hardware acceleration (WHPX or HAXM). 2. Allocate adequate RAM (minimum 2 GB for modern OS). 3. Use qcow2 disk format. 4. Enable OpenGL if available. 5. Reduce vCPU count if host is overloaded.

**Q: Display doesn't show — what should I check?**
A: 1. Check display backend setting (SDL, VNC, etc.). 2. For VNC: connect to `127.0.0.1:5900`. 3. For SDL: ensure SDL library is installed. 4. Try "None" display + SSH for headless access. 5. Check if guest OS has a graphical desktop installed.

### 15.11 Advanced

**Q: Can I use VM-Harness with libvirt?**
A: Not directly. VM-Harness controls QEMU instances directly via QMP and SSH. Libvirt uses its own management layer. If you need libvirt integration, you would need to start VMs through libvirt and connect VM-Harness to the QMP socket libvirt exposes.

**Q: How do I contribute to VM-Harness?**
A: See the [Contributing Guide](#16-contributing-guide) for detailed instructions on setting up a development environment, running tests, and submitting changes.

**Q: Where can I get help?**
A: - **User Guide:** This document
- **Troubleshooting Guide:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **FAQ:** This section
- **GitHub Issues:** Open an issue on the repository
- **MCP Server:** Use the MCP tools for programmatic control
- **Agentic Chat:** Ask the AI for help (if you have a provider configured)

**Q: What is the MCP server?**
A: The MCP (Model Context Protocol) server allows AI agents to control VM-Harness programmatically. It exposes tools like `vm_start`, `vm_stop`, `guest_exec`, `guest_file_read`, `snapshot_create`, `iso_list`, and `get_usage`. This enables AI agents (like Claude, GPT-4) to manage VMs through natural language.

**Q: Is there a REST API?**
A: Yes. VM-Harness includes a REST API server for programmatic control. Start it with `qemu-mcp api start --port 8080`. The API provides endpoints for VM control, guest operations, snapshots, ISOs, and more.

---

## 16. Contributing Guide

## 16. Contributing Guide

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/qemu-mcp.git
cd qemu-mcp

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install dependencies with dev tools
pip install -e ".[dev]"

# Verify installation
qemu-mcp status
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_panel_name.py -v

# Run with coverage
pytest tests/ --cov=gui --cov-report=html
```

### Project Structure

```
VM-Harness/
├── gui/                          # PyQt5 GUI (25+ modules)
│   ├── __main__.py              # GUI entry point
│   ├── main_window.py           # Main window, sidebar, panel stack
│   ├── theme.py                 # Theme constants (colors, spacing, fonts)
│   ├── widgets.py               # Reusable widgets (Card, StatusIndicator, etc.)
│   ├── panels*.py               # Individual panel modules (25+ files)
│   ├── qmp_bridge.py            # QMP async bridge with PyQt5 signals
│   ├── ssh_bridge.py            # SSH async bridge
│   ├── chat_engine.py           # Agentic chat engine with tool executor
│   ├── api_providers.py         # API provider management
│   ├── provider_store.py        # Provider configuration store
│   ├── credential_store.py      # Encrypted credential vault
│   ├── iso_manager.py           # ISO file management
│   ├── multi_vm.py              # Multi-VM manager
│   ├── snapshot_scheduler.py    # Snapshot scheduler
│   ├── metrics_store.py         # Metrics storage for telemetry
│   └── ...
├── tests/                        # Test suite
├── dist/                         # PyInstaller executable output
│   └── VM-Harness.exe             # Standalone Windows executable
├── docs/                         # Documentation
│   ├── USER_GUIDE.md            # This file
│   ├── FAQ.md                   # Frequently asked questions
│   ├── TROUBLESHOOTING.md       # Troubleshooting guide
│   └── AGENT_GUIDE.md           # AI agent integration guide
├── .env                          # Configuration file (auto-generated)
├── pyproject.toml               # Project metadata and dependencies
└── README.md                    # Project overview
```

### Adding a New Panel

1. **Create the panel file:** `gui/panels_<name>.py`
2. **Follow the existing panel pattern:**
   ```python
   from __future__ import annotations
   
   from gui.theme import T
   from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
   from gui.widgets import Card
   
   class NewPanel(QWidget):
       def __init__(self, parent=None):
           super().__init__(parent)
           self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
           layout = QVBoxLayout(self)
           layout.setContentsMargins(16, 16, 16, 16)
           layout.setSpacing(12)
           
           # Add your UI components here
           card = Card("Section Title")
           layout.addWidget(card)
   ```
3. **Register the panel in `gui/main_window.py`:**
   - Add import: `from gui.panels_<name> import NewPanel`
   - Add to PANELS list in Sidebar class: `("Panel Name", "🔤", "<name>")`
   - Add to panel_list in `_build_panels()`: `(NewPanel, "<name>")`
   - Wire any required bridges in `_build_panels()`
4. **Add tests** in `tests/` directory

### Panel Design Guidelines

| Guideline | Description |
|-----------|-------------|
| **Inherit from QWidget** | All panels are QWidget subclasses |
| **Use Card widgets** | Group related content in Card widgets for consistent styling |
| **Apply theme styles** | Use `T` constants from `gui.theme` for colors, spacing, fonts |
| **Dark background** | Set `background: T.BG_PRIMARY` on the panel |
| **Layout margins** | Use `setContentsMargins(16, 16, 16, 16)` for consistent spacing |
| **Signal connections** | Connect to QMP/SSH bridges via `set_qmp_bridge()` / `set_ssh_bridge()` patterns |
| **Single responsibility** | Each panel should focus on one functional area |

### Code Style

- **Type hints:** Use `from __future__ import annotations` and type annotations
- **PEP 8:** Follow Python style guidelines
- **PyQt5 conventions:** Use signals/slots for async communication
- **Graceful degradation:** Handle missing dependencies gracefully (e.g., WMI for USB)
- **Docstrings:** Document classes and public methods

### Dependency Management

**Core Dependencies** (from `pyproject.toml`):
```
mcp[cli]>=1.0.0      # Model Context Protocol
pydantic>=2.0.0       # Data validation
pydantic-settings>=2.0.0
python-dotenv>=1.0.0  # .env file parsing
asyncssh>=2.14.0      # SSH communication
loguru>=0.7.0         # Logging
cryptography>=42.0.0  # Fernet encryption
matplotlib>=3.8.0     # Charts
psutil>=5.9.0         # Process monitoring
PyQt5>=5.15.0         # GUI framework
aiohttp>=3.9.0        # HTTP client
```

**Optional Dependencies** (dev):
```
pytest>=8.0.0         # Testing
pytest-asyncio>=0.23.0
```

### Submitting Changes

1. **Fork** the repository
2. **Create a feature branch:** `git checkout -b feature/my-feature`
3. **Make changes** following the code style guidelines
4. **Add/Update tests** for new functionality
5. **Run tests:** `pytest tests/ -v`
6. **Commit** with clear messages: `git commit -m "Add feature X"`
7. **Push** to your fork: `git push origin feature/my-feature`
8. **Open a Pull Request** with:
   - Description of changes
   - Screenshots (for UI changes)
   - Test results

### Code Review Checklist

- [ ] Panel follows existing patterns and styling
- [ ] Type hints used throughout
- [ ] Error handling is graceful (no crashes)
- [ ] Dependencies are properly handled (try/except for optional)
- [ ] Tests cover new functionality
- [ ] Documentation updated if needed

### Reporting Issues

Use the GitHub issue tracker. Include:

1. **VM-Harness version** (from `gui/__main__.py` or `pyproject.toml`)
2. **Python version:** `python --version`
3. **QEMU version:** `qemu-system-x86_64 --version`
4. **Operating system** and version
5. **Description** of the issue
6. **Steps to reproduce**
7. **Expected behavior** vs actual behavior
8. **Relevant error messages/logs** (from Logs panel or terminal)

### Release Process

1. Update version in `pyproject.toml`
2. Update documentation
3. Build executable: `pyinstaller --onefile --windowed --name VM-Harness gui/__main__.py`
4. Test the executable
5. Create release with:
   - Source code archive
   - `VM-Harness.exe`
   - Updated documentation

---

*Documentation version: 1.0.0 | VM-Harness v1.0.0*
*Developed by Omarchy VM Control | Released under MIT License*
