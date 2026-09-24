# VM-Harness FAQ

**Frequently Asked Questions**

---

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation & Setup](#installation--setup)
3. [VM Management](#vm-management)
4. [Networking](#networking)
5. [Snapshots](#snapshots)
6. [Security & Credentials](#security--credentials)
7. [AI Chat](#ai-chat)
8. [API Providers](#api-providers)
9. [Multi-VM](#multi-vm)
10. [USB & Hardware](#usb--hardware)
11. [Troubleshooting](#troubleshooting)
12. [Advanced](#advanced)

---

## General Questions

### What is VM-Harness?

VM-Harness is a comprehensive desktop application for controlling QEMU virtual machines. It provides:

- **25+ GUI Panels** — Complete VM control from a polished dark-themed PyQt5 desktop interface
- **CLI Tool** — Command-line interface for scripting (`qemu-mcp`)
- **REST API** — HTTP endpoints for programmatic control
- **MCP Server** — AI agent tools via Model Context Protocol
- **Agentic AI Chat** — Natural language VM control via LLM integration
- **Self-Healing** — Atomic state management, process guardian, automatic recovery

### What makes VM-Harness different from other VM managers?

| Feature | VM-Harness | Traditional VM Managers |
|---------|----------|------------------------|
| **AI Integration** | Built-in agentic chat with tool execution | Rarely available |
| **Self-Healing** | Atomic state, process guardian, auto-recovery | Not common |
| **Multi-VM** | Control multiple QEMU instances from one interface | Often limited |
| **Panel Coverage** | 25+ specialized panels for every aspect | Varies |
| **USB Passthrough** | WMI-based hotplug with auto-attach | Often missing |
| **Snapshot Scheduling** | Automated background snapshots with retention | Manual only |

### Which platforms are supported?

VM-Harness is **tested and supported on Windows 10/11** with WHPX hardware acceleration.

**Platform Support:**

| Platform | Status | Notes |
|----------|--------|-------|
| Windows 10/11 | ✅ Fully supported | WHPX acceleration, WMI USB enumeration |
| Linux | ⚠️ Should work | PyQt5 compatible, but untested |
| macOS | ⚠️ Should work | PyQt5 compatible, but untested |

The code is written to be cross-platform (PyQt5, Python standard library), but testing is Windows-only.

### Is VM-Harness open source?

Yes. VM-Harness is open-source software released under the **MIT License**.

- **Repository:** `https://github.com/your-org/qemu-mcp`
- **License:** MIT (see LICENSE file)
- **Author:** Omarchy VM Control

### What version of Python do I need?

- **Minimum:** Python 3.10
- **Recommended:** Python 3.11 or 3.13

Python 3.11+ is recommended for full async feature support.

---

## Installation & Setup

### How do I install VM-Harness?

See the [Installation section](USER_GUIDE.md#2-installation) in the User Guide for detailed steps.

**Quick install:**
```bash
git clone https://github.com/your-org/qemu-mcp.git
cd qemu-mcp
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
qemu-mcp gui
```

### Where can I get QEMU?

Download QEMU from [qemu.org](https://www.qemu.org/download/):

| Platform | Method |
|----------|--------|
| **Windows** | Use the Windows installer or extract pre-built binaries to `C:\Program Files\qemu\` |
| **Linux** | `sudo apt install qemu-system-x86` (Debian/Ubuntu) or equivalent |
| **macOS** | `brew install qemu` |

**Windows QEMU path:** `C:/Program Files/qemu/qemu-system-x86_64.exe`

### Do I need to install anything besides QEMU and Python?

**Required:**
- Python 3.11+ (3.13 recommended)
- QEMU (qemu-system-x86_64)

**Auto-installed by pip:**
- PyQt5 (GUI framework)
- All Python dependencies (mcp, pydantic, asyncssh, cryptography, matplotlib, etc.)

**Recommended Windows Features:**
- Windows Hypervisor Platform (for WHPX acceleration)
- Virtual Machine Platform (for WHPX acceleration)

**Optional:**
- Git (to clone the repository)
- PyInstaller (to build the standalone EXE)

### Can I install VM-Harness without Python?

**Yes, if using the standalone EXE.**

The `dist/VM-Harness.exe` is a self-contained PyInstaller build that bundles:
- Python interpreter
- All dependencies (PyQt5, etc.)
- Application code

No Python installation is required on the target machine when using the EXE.

To build the EXE yourself:
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name VM-Harness gui/__main__.py
```

---

## VM Management

### How do I start a VM?

**GUI Method:**
1. Launch the GUI: `qemu-mcp gui`
2. Go to the **Dashboard** panel (default)
3. Click **▶ Start VM**
4. Status indicator turns green when running

**CLI Method:**
```bash
qemu-mcp vm start <vm-name>
```

**AI Chat Method:**
```
You: Start my VM
AI: Starting the VM...
Tool: vm_start
AI: VM started successfully.
```

### How do I stop a VM?

**GUI Method:**
1. Click **■ Stop VM** on the Dashboard
2. The VM receives a graceful ACPI shutdown signal

**CLI Method:**
```bash
qemu-mcp vm stop <vm-name>
```

**Note:** If the VM doesn't respond to ACPI, use the **Reset** button for a forced reset.

### Can I run multiple VMs simultaneously?

**Yes.** Use the **VM Switcher** panel to manage multiple VMs.

**Adding a VM:**
1. Open **VM Switcher** panel
2. Click **Add VM**
3. Enter VM name and select disk image
4. Configure resource limits (RAM, CPUs, priority)

**Switching Between VMs:**
1. Select a VM in the list
2. Click **Switch To**
3. Other panels (Dashboard, VM Control, etc.) now target the active VM

Each VM can be independently started, stopped, reset, suspended, and have snapshots created.

### How do I change VM resources (RAM, CPU)?

**Method 1: Settings Panel**
1. Go to **Settings > VM** tab
2. Adjust RAM (MB) and vCPUs values
3. Click **Save Settings**
4. **Restart the VM** for changes to take effect

**Method 2: VM Switcher**
1. Select a VM in **VM Switcher**
2. Adjust resource limits in the Resource Limits section
3. Click **Apply Limits**

**Important:** Resource hotplug is limited. RAM and CPU changes typically require a VM restart.

| Resource | Valid Range | Default |
|----------|-------------|---------|
| RAM | 256 MB - 131072 MB (128 GB) | 16384 MB (16 GB) |
| vCPUs | 1 - 128 | 8 |

### How do I access the guest OS?

**Option 1: SSH Terminal (Recommended)**
- Go to **Guest Terminal** panel
- Click **Connect to Guest**
- Default: `127.0.0.1:2222`, user: `omarchyvm`
- Execute commands interactively with history

**Option 2: Guest Agent**
- Go to **Guest Agent** panel
- Browse files, execute commands, manage processes and services
- Tabs: Guest Info, Processes, Services, File Browser, Network

**Option 3: Display (VNC/SPICE)**
- Configure VNC or SPICE in **Settings > Display**
- Connect with a VNC/SPICE client

### Why can't I see the VM display?

**If using SDL or GTK display:**
- The display window should appear automatically when the VM starts
- Check that your QEMU binary supports the selected display backend

**If using VNC:**
- Note the VNC port (default: 5900)
- Connect with a VNC client to `127.0.0.1:5900`
- VNC settings are in **Display** panel > Remote Access tab

**If using "None" display:**
- The VM runs headless (no GUI)
- Use SSH or VNC to access the guest

**If using SPICE:**
- Install SPICE client (virt-viewer, spicy)
- Connect to the SPICE port (default: 5930)

### How do I mount an ISO?

1. Go to **ISO Manager** panel
2. Import or select an ISO file (Internal or External tab)
3. In **VM Control** panel, the ISO can be mounted via QMP
4. Or configure `VM_ISO` in `.env`

The ISO is mounted as a virtual CD-ROM. If `AUTO_EJECT_ISO` is enabled (default), it's automatically ejected after boot.

### What is hardware acceleration and which mode should I use?

| Mode | Description | Performance | Requirements |
|------|-------------|-------------|--------------|
| **WHPX** (default) | Windows Hypervisor Platform | Best on Windows | Windows 10/11 with WHPX enabled |
| **HAXM** | Intel Hardware Accelerator | Good | Intel VT-x, HAXM driver installed |
| **TCG** | Software emulation | Very slow (10-100x) | None (always works) |

**Recommendation:** Use **WHPX** on Windows 10/11 for best performance.

**To enable WHPX:**
1. Open PowerShell as Administrator
2. Run: `Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform`
3. Restart your computer
4. Select WHPX in **Settings > Acceleration**

### How do I create a new VM?

Use the **Create VM** wizard (5-step provisioning):

1. **Identity:** VM name, OS type, machine type, firmware
2. **Hardware:** CPUs, RAM, host passthrough, I/O threads
3. **Storage:** Disk size, format (qcow2/raw/vmdk/vhd), cache mode, ISO
4. **Network:** NAT/Bridged/Isolated, port forwards
5. **Confirm:** Review and create

The wizard creates:
- Directory: `~/Virtual Machines/<vm-name>/`
- Disk: `qemu-img create -f qcow2 disk.qcow2 <size>G`

---

## Networking

### How do I SSH into the VM?

**Default Connection:**
```
ssh -p 2222 omarchyvm@127.0.0.1
```

**Requirements:**
1. VM must be running
2. SSH server must be running inside the guest
3. Port forwarding configured: host 2222 → guest 22

**To set up SSH in the guest (Linux):**
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install openssh-server
sudo systemctl enable sshd
sudo systemctl start sshd
```

### Can the VM access the internet?

**Yes, with NAT networking (the default).**

The VM shares the host's network connection for outbound traffic. Inbound connections require port forwarding.

### How do I access the VM from other devices on my network?

Configure **Bridged** networking instead of NAT:

1. Go to **Network > Virtual Networks** tab
2. Click **Add Network**
3. Select **Bridged** type
4. The VM gets its own IP on your local network

### How do I set up port forwarding?

1. Go to **Network > Port Forwarding** tab
2. Click **Add Rule**
3. Configure:
   - VM name
   - Protocol (TCP/UDP)
   - Host port (e.g., 2222)
   - Guest port (e.g., 22)
4. Click OK

**Example: Web server access**
- Host Port: 8080
- Guest Port: 80
- Protocol: TCP
- Access: `http://127.0.0.1:8080`

### What firewall rules can I configure?

In **Network > Firewall Rules** tab:

| Rule Field | Description | Example |
|------------|-------------|---------|
| Chain | iptables chain | input, output, forward |
| Source | Source IP/network | 192.168.1.0/24 |
| Destination | Destination IP/network | 10.0.0.0/8 |
| Port | Port number or range | 22, 80:443 |
| Action | accept, reject, drop | accept |
| Enabled | Toggle rule on/off | Yes/No |

---

## Snapshots

### What is a snapshot?

A snapshot captures the complete state of the VM's disk at a point in time. You can restore the VM to that exact state later, undoing any changes made after the snapshot.

**Technical:** QEMU snapshots are implemented via `qemu-img` on qcow2 disk images.

### How do I create a snapshot?

**GUI:** Go to **Snapshots** panel, click **Create**, enter a name.

**CLI:** `qemu-mcp snapshot create <name>`

**Chat:** "Create a snapshot called <name>"

**Backend command:** `qemu-img snapshot -c <name> <disk-path>`

### How do I restore a snapshot?

1. Go to **Snapshots** panel
2. Select the snapshot from the list
3. Click **Restore**
4. Confirm: "Restore snapshot '{name}'? Current state will be lost."

**Warning:** Restoring a snapshot **discards all changes** made since the snapshot was created.

**Backend command:** `qemu-img snapshot -a <name> <disk-path>`

### How do I delete a snapshot?

1. Select the snapshot in the **Snapshots** panel
2. Click **Delete**
3. Confirm: "Delete snapshot '{name}'? This cannot be undone."

**Backend command:** `qemu-img snapshot -d <name> <disk-path>`

### Can I snapshot a running VM?

**Yes, but with caveats:**

For data consistency, it's recommended to:
- Pause the VM first, or
- Use external snapshot tools

QEMU supports internal snapshots via `qemu-img`, which work on running VMs but may capture in-flight I/O.

### How many snapshots can I have?

**No hard limit**, but:
- Each snapshot consumes disk space
- Having many snapshots can slightly slow disk operations
- The Snapshot Scheduler can automatically manage retention

**Snapshot Scheduler Settings** (in **Settings > Snapshots**):
- Enabled: Toggle scheduling on/off
- Interval: Time between snapshots (minutes)
- Retention: Max snapshots to keep (default: 10)
- Name prefix: Prefix for auto-generated names (default: `auto-`)

---

## Security & Credentials

### Where are my credentials stored?

Encrypted in:
```
~/.local/share/vmharness/credentials.json
```

**Encryption:** Fernet symmetric encryption (from the `cryptography` library).

The encryption key is derived from the system. For production use, consider a dedicated secrets manager.

### What credential types are supported?

| Type | Description | Example Use |
|------|-------------|-------------|
| `password` | Generic passwords | VM passwords, service accounts |
| `ssh_key` | SSH private keys | Guest SSH authentication |
| `api_key` | API keys | OpenAI, Anthropic, OpenRouter keys |
| `qmp_pass` | QMP connection passwords | QMP authentication |
| `other` | Other secret types | Any custom secret |

### Can I use SSH keys instead of passwords?

**Yes.** Configure `SSH_PRIVATE_KEY` in `.env` with the path to your SSH private key.

The SSH bridge will use key-based authentication instead of password authentication.

### How do I enable authentication for the API/MCP server?

1. Go to **Settings > Auth** tab
2. Set Auth Method to `api_key` or `jwt`
3. Configure the API key in the **Security** panel
4. Clients must send `Authorization: Bearer <token>` on each request

**Auth Methods:**

| Method | Description |
|--------|-------------|
| `none` | No authentication (default, development only) |
| `api_key` | Simple API key in Authorization header |
| `jwt` | JSON Web Token validation |

---

## AI Chat

### How do I use the Agentic Chat?

1. **Configure an API provider** in the **API Providers** panel
2. Go to **Chat** panel
3. Select your provider from the dropdown
4. Type a natural language request
5. The AI responds and can execute QEMU tools

**Example:**
```
You: Is my VM running?
AI: Let me check the VM status for you.
[Tool: vm_status]
AI: Your VM "omarchy-vm" is currently running with 8 GB RAM and 4 vCPUs.
```

### Which AI providers are supported?

| Provider | Base URL | Get API Key |
|----------|----------|-------------|
| **OpenRouter** | `https://openrouter.ai/api/v1` | [openrouter.ai](https://openrouter.ai) |
| **Anthropic** | `https://api.anthropic.com/v1` | [anthropic.com](https://anthropic.com) |
| **OpenAI** | `https://api.openai.com/v1` | [platform.openai.com](https://platform.openai.com) |
| **Google** | `https://generativelanguage.googleapis.com/v1` | [makersuite.google.com](https://makersuite.google.com) |
| **Custom** | Any OpenAI-compatible API | Your provider |

### What can the chat control?

| Tool | Description | Example Prompt |
|------|-------------|----------------|
| `vm_status` | Get VM status | "Is my VM running?" |
| `vm_start` | Start the VM | "Start my virtual machine" |
| `vm_stop` | Stop the VM | "Shut down the VM" |
| `vm_reset` | Reset the VM | "Restart the VM" |
| `vm_suspend` | Suspend VM | "Pause the VM" |
| `vm_resume` | Resume VM | "Resume the VM" |
| `guest_exec` | Execute command | "Run uname -a in the guest" |
| `guest_file_read` | Read file | "Show me /etc/os-release" |
| `guest_file_write` | Write file | "Create a config file" |
| `guest_file_list` | List files | "List /tmp directory" |
| `guest_file_remove` | Remove file | "Delete the temp file" |
| `snapshot_create` | Create snapshot | "Take a snapshot named backup" |
| `snapshot_list` | List snapshots | "What snapshots exist?" |
| `snapshot_restore` | Restore snapshot | "Restore the backup snapshot" |
| `iso_list` | List ISOs | "What ISOs are available?" |
| `iso_import` | Import ISO | "Import this ISO file" |
| `get_usage` | Get usage stats | "How much RAM is used?" |

### Why did my chat request fail?

**Common reasons:**

| Error | Cause | Solution |
|-------|-------|----------|
| "No provider configured" | No API key set | Configure API key in Providers panel |
| "VM not running" | VM is stopped | Start the VM first |
| "SSH unreachable" | No SSH server in guest | Install SSH server in guest |
| "QMP disconnected" | QMP connection lost | Restart VM or check QMP settings |
| "Tool error" | Tool-specific failure | Check error message for details |

### Can I add a custom AI provider?

**Yes.** Use the **Add Custom** button in the API Providers panel:

1. Provider name (e.g., "My Custom API")
2. Base URL (e.g., `https://api.example.com/v1`)
3. Model name (e.g., `gpt-4`)
4. API key (optional)

The provider must be OpenAI-compatible (same API format).

---

## Multi-VM

### How do I add a new VM?

1. Open **VM Switcher** panel
2. Click **Add VM**
3. Enter VM name
4. Select disk image (`.qcow2`, `.img`, `.vmdk`, `.raw`)
5. Configure resource limits (RAM, CPUs, priority)
6. Click OK

The VM appears in the list with a ○ (stopped) indicator.

### How do I clone a VM?

1. Select a VM in **VM Switcher**
2. Click **Clone**
3. The **Clone Dialog** opens
4. Specify new name and destination
5. The disk is copied using `qemu-img convert`

### What are VM templates?

Templates are pre-configured VM configurations that can be reused.

1. Click **Templates** in VM Switcher
2. Open the **Template Manager**
3. Save current VM config as a template
4. Create new VMs from templates

### How do resource limits work?

Per-VM resource limits in **VM Switcher**:

| Limit | Range | Description |
|-------|-------|-------------|
| Max RAM | 512 MB - GLOBAL_MAX_RAM_MB | Maximum memory the VM can use |
| Max vCPUs | 1 - GLOBAL_MAX_CPUS | Maximum CPU cores allocated |
| Priority | 1 (highest) - 10 (lowest) | Scheduling priority |

---

## USB & Hardware

### How do I attach a USB device to my VM?

1. Go to **USB & Devices > USB Devices** tab
2. Select a USB device from the list
3. Click **Attach to VM**
4. The device is attached via QMP `device_add` with `usb-host` driver

**Requirements:**
- QMP connection to the running VM
- WMI available (Windows) for device enumeration
- QMP `device_add`/`device_del` support

### How do I detach a USB device?

1. Select the attached device (Assigned = Yes)
2. Click **Detach**
3. The device is removed via QMP `device_del`

### What is auto-attach?

Enable **Auto-attach on VM start** to automatically reattach a USB device when the VM starts.

Configuration is persisted in `~/.qemu-mcp/usb_config.json`.

### What is PCI passthrough?

PCI passthrough allows passing through host PCI devices to the VM:

- **GPU:** NVIDIA RTX 3080, Intel HD Graphics
- **Storage:** NVMe SSDs
- **Other:** USB controllers, network cards

Requires IOMMU/VFIO setup on the host.

### What is TPM and when do I need it?

**vTPM 2.0** is a virtual Trusted Platform Module:

- Required for **Windows 11** guests
- Provides secure key storage and attestation
- Configured in **USB & Devices > TPM / Secure Boot** tab

**UEFI Secure Boot:**
- Verifies boot chain integrity
- Prevents unauthorized bootloaders
- Recommended for security-conscious deployments

---

## Troubleshooting

### QEMU won't start

See [Troubleshooting Guide](TROUBLESHOOTING.md#1-qemu-not-found).

**Common causes:**
- QEMU binary path incorrect
- QEMU not installed
- Missing dependencies

### SSH connection fails

See [Troubleshooting Guide](TROUBLESHOOTING.md#2-ssh-failures).

**Common causes:**
- VM not running
- SSH server not running in guest
- Port conflict on host (2222)
- Wrong credentials

### QMP errors

See [Troubleshooting Guide](TROUBLESHOOTING.md#3-qmp-failures).

**Common causes:**
- QMP port not accessible (4444)
- QEMU not started with QMP enabled
- Firewall blocking connection

### VM is very slow

**Solutions:**
1. Use hardware acceleration (WHPX or HAXM)
2. Allocate adequate RAM (minimum 2 GB for modern OS)
3. Use qcow2 disk format
4. Enable OpenGL if available
5. Reduce vCPU count if host is overloaded

### Display doesn't show

- Check display backend setting (SDL, VNC, etc.)
- For VNC: connect to `127.0.0.1:5900`
- For SDL: ensure SDL library is installed
- Try "None" display + SSH for headless access

---

## Advanced

### Can I use VM-Harness with libvirt?

**Not directly.** VM-Harness controls QEMU instances directly via QMP and SSH. Libvirt uses its own management layer.

If you need libvirt integration, you would need to:
1. Start VMs through libvirt
2. Connect VM-Harness to the QMP socket libvirt exposes

### How do I contribute to VM-Harness?

See the [Contributing Guide](USER_GUIDE.md#16-contributing-guide) in the User Guide.

### Where can I get help?

- **User Guide:** [USER_GUIDE.md](USER_GUIDE.md)
- **Troubleshooting Guide:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub Issues:** Open an issue on the repository
- **MCP Server:** Use the MCP tools for programmatic control

### What is the MCP server?

The MCP (Model Context Protocol) server allows AI agents to control VM-Harness programmatically. It exposes tools like:

- `vm_start`, `vm_stop`, `vm_reset`
- `guest_exec`, `guest_file_read`, `guest_file_write`
- `snapshot_create`, `snapshot_list`, `snapshot_restore`
- `iso_list`, `iso_import`
- `get_usage`

This enables AI agents (like Claude, GPT-4) to manage VMs through natural language.

---

*Last updated: September 2026*
