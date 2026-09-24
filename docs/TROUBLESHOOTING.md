# VM-Harness Troubleshooting Guide

**Diagnosing and resolving common issues**

---

## Table of Contents

1. [QEMU Not Found](#1-qemu-not-found)
2. [SSH Failures](#2-ssh-failures)
3. [QMP Failures](#3-qmp-failures)
4. [VM Won't Start](#4-vm-wont-start)
5. [Display Issues](#5-display-issues)
6. [Acceleration Problems](#6-acceleration-problems)
7. [Network Issues](#7-network-issues)
8. [Snapshot Errors](#8-snapshot-errors)
9. [GUI Problems](#9-gui-problems)
10. [Performance Issues](#10-performance-issues)
11. [Debugging Tips](#11-debugging-tips)

---

## 1. QEMU Not Found

### Symptoms

- Error message: "QEMU binary not found"
- QEMU fails to launch
- VM status shows "Stopped" immediately

### Diagnostic Steps

**Step 1: Verify QEMU is installed**

```bash
qemu-system-x86_64 --version
```

If this fails, QEMU is not installed or not in your PATH.

**Step 2: Check QEMU binary path**

1. Open **Settings > QEMU** tab
2. Check the "QEMU Binary" field
3. Verify the path points to a valid executable

Common Windows paths:
```
C:/Program Files/qemu/qemu-system-x86_64.exe
C:/qemu/qemu-system-x86_64.exe
C:/Users/<user>/qemu/qemu-system-x86_64.exe
```

**Step 3: Check file existence**

```bash
# In PowerShell or CMD
test-path "C:/Program Files/qemu/qemu-system-x86_64.exe"
# Or in Git Bash
ls -la "/c/Program Files/qemu/qemu-system-x86_64.exe"
```

### Solutions

**Solution 1: Install QEMU**

Download from [qemu.org](https://www.qemu.org/download/):

- **Windows:** Use the Windows installer from the QEMU website
- Extract to a known location (e.g., `C:/Program Files/qemu/`)

**Solution 2: Fix the path in Settings**

1. Go to **Settings > QEMU** tab
2. Update the QEMU Binary field with the correct path
3. Click **Save Settings**
4. Restart the application

**Solution 3: Add QEMU to PATH**

Add QEMU's directory to your system PATH environment variable:

```bash
# In System Environment Variables
# Add: C:\Program Files\qemu
```

Then restart your terminal/IDE.

---

## 2. SSH Failures

### Symptoms

- "Connection refused" when connecting via SSH
- Connection timeout
- "No SSH server in guest VM" error
- Guest Terminal shows disconnected

### Diagnostic Steps

**Step 1: Verify VM is running**

Check the Dashboard — the status indicator should be green.

**Step 2: Check SSH port forwarding**

1. Go to **Settings > Network** tab
2. Verify SSH Host is `127.0.0.1`
3. Verify SSH Port is `2222` (or your configured port)
4. Check that QEMU was started with port forwarding:
   ```
   -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22
   ```

**Step 3: Check for port conflicts**

```bash
# Check if port 2222 is in use
netstat -an | findstr 2222
# Or
Get-NetTCPConnection -LocalPort 2222  # PowerShell
```

If another process is using the port, QEMU cannot set up forwarding.

**Step 4: Verify SSH server in guest**

The guest VM must have an SSH server running. Check inside the guest:

```bash
# For Linux guests with console access
sudo systemctl status sshd
# Or
sudo ss -tlnp | grep :22
```

### Solutions

**Solution 1: Install SSH server in guest**

For Linux guests:
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install openssh-server
sudo systemctl enable sshd
sudo systemctl start sshd

# Or use dropbear (lightweight)
sudo apt install dropbear
```

For Windows guests:
- Enable OpenSSH Server in Windows Features
- Or use a third-party SSH server

**Solution 2: Change SSH port**

If port 2222 is conflicted:

1. Go to **Settings > Network**
2. Change SSH Port to an unused port (e.g., `2223`)
3. Update QEMU command line to use the new port
4. Restart the VM

**Solution 3: Check credentials**

Verify in **Settings > Network**:
- SSH Username: default is `omarchyvm`
- SSH Password or SSH Private Key is configured

Test credentials manually:
```bash
ssh -p 2222 omarchyvm@127.0.0.1
```

**Solution 4: Restart the VM**

Sometimes port forwarding doesn't establish correctly. Restart the VM to reinitialize networking.

---

## 3. QMP Failures

### Symptoms

- "QMP disconnected" error
- VM control operations (start/stop/reset) fail
- QMP Console shows no response
- QMP System Info shows no data

### Diagnostic Steps

**Step 1: Check QMP configuration**

1. Go to **Settings** panel
2. Verify QMP settings (these are typically in `.env`):
   ```
   QMP_HOST=127.0.0.1
   QMP_PORT=4444
   ```

**Step 2: Verify QMP socket**

QEMU must be started with QMP enabled. Check the QEMU command line includes:
```
-qmp tcp:127.0.0.1:4444,server,nowait
```

Or for Unix sockets (Linux/macOS):
```
-qmp unix:/tmp/qmp.sock,server,nowait
```

**Step 3: Check if QEMU process is running**

```bash
# Windows
tasklist | findstr qemu

# Linux
ps aux | grep qemu
```

**Step 4: Test QMP connectivity**

```bash
# Using telnet or netcat
telnet 127.0.0.1 4444
# Or
nc 127.0.0.1 4444
```

You should see a QMP greeting message if connected.

### Solutions

**Solution 1: Restart QEMU with QMP**

Ensure QEMU is launched with QMP enabled. If using VM-Harness, this is handled automatically when the VM starts through the GUI.

**Solution 2: Check firewall rules**

Windows Firewall or other security software may block port 4444.

1. Open Windows Defender Firewall
2. Check inbound rules for port 4444
3. Add an exception if needed

**Solution 3: Use a different QMP port**

If port 4444 is conflicting:

1. Edit `.env`:
   ```
   QMP_PORT=4445
   ```
2. Restart the VM

**Solution 4: Reconnect QMP**

In the QMP Console panel, try reconnecting. The QMP bridge should auto-reconnect on disconnection.

---

## 4. VM Won't Start

### Symptoms

- Start button clicked but VM doesn't start
- Error message appears
- VM status remains "Stopped"

### Diagnostic Steps

**Step 1: Check disk image**

1. Go to **Settings > VM** tab
2. Verify the Disk Path points to an existing qcow2 file
3. Check disk integrity:
   ```bash
   qemu-img check <disk-path>
   ```

**Step 2: Validate resource settings**

- RAM: Must be at least 256 MB, maximum 131072 MB
- CPUs: Must be at least 1, maximum 128

**Step 3: Check for conflicting VMs**

If another VM is using the same resources or disk, startup may fail.

### Solutions

**Solution 1: Fix disk path**

If the disk doesn't exist:
1. Create a new disk in **Storage** panel
2. Or update the disk path to an existing image

**Solution 2: Create a new VM**

Use the **Create VM** wizard (5-step provisioning):
1. Name and basic config
2. Disk selection/creation
3. ISO selection (optional)
4. Resource allocation
5. Review and create

**Solution 3: Check QEMU logs**

Run QEMU manually to see error output:
```bash
qemu-system-x86_64 -drive file=<disk>,format=qcow2 -m 8192 -smp 4
```

---

## 5. Display Issues

### Symptoms

- No display window appears
- Display window is blank/black
- VNC connection fails

### Solutions

**SDL/GTK Display:**

- Ensure the QEMU binary supports the selected display backend
- Check that SDL libraries are installed (for SDL display)
- Try a different display backend in **Settings > Display**

**VNC Display:**

1. Note the VNC port (default: 5900, or configured)
2. Connect with a VNC client:
   - RealVNC, TightVNC, TigerVNC
   - Connection: `127.0.0.1:5900`
3. If VNC port is different, check QEMU command line for `-vnc :<port>`

**SPICE Display:**

1. Install SPICE client (virt-viewer, spicy)
2. Connect to the SPICE port
3. Configure SPICE settings in **Settings > Display**

**Headless (None) Display:**

- The VM runs without a display
- Use SSH, VNC, or SPICE to access the guest
- This is useful for servers and background workloads

---

## 6. Acceleration Problems

### Symptoms

- VM runs very slowly
- "Hardware acceleration not available" warning
- High CPU usage with low performance

### Acceleration Modes

| Mode | Description | Requirements |
|------|-------------|--------------|
| **WHPX** | Windows Hypervisor Platform | Windows 10/11, WHPX enabled |
| **HAXM** | Intel Hardware Accelerator | Intel VT-x, HAXM driver installed |
| **TCG** | Software emulation | None (always works, very slow) |

### Diagnostic Steps

**Step 1: Check acceleration mode**

1. Go to **Settings > Acceleration** tab
2. Check the selected mode (WHPX, HAXM, or TCG)

**Step 2: Verify WHPX is enabled (Windows)**

1. Open "Turn Windows features on or off"
2. Check "Windows Hypervisor Platform"
3. Check "Virtual Machine Platform"
4. Restart if you made changes

**Step 3: Verify HAXM (Intel systems)**

```bash
# Check if HAXM is loaded
sc query hax
# Or check device manager for "Intel HAXM"
```

### Solutions

**Solution 1: Enable WHPX (recommended for Windows)**

1. Open PowerShell as Administrator:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName WindowsHypervisorPlatform
   ```
2. Restart your computer
3. Select WHPX in **Settings > Acceleration**

**Solution 2: Install HAXM**

Download from [Intel HAXM](https://github.com/intel/haxm):
1. Run the installer
2. Select HAXM in **Settings > Acceleration**

**Solution 3: Use TCG (slow, last resort)**

If hardware acceleration is unavailable:
1. Select TCG in **Settings > Acceleration**
2. Warning: VM will be 10-100x slower
3. Only use for debugging or when no other option exists

---

## 7. Network Issues

### Symptoms

- VM cannot access internet
- Port forwarding doesn't work
- Cannot reach VM from host

### Solutions

**No Internet in VM:**

1. Verify NAT networking is configured
2. Check host internet connection
3. Try bridged networking for direct access

**Port Forwarding Not Working:**

1. Verify the VM is running
2. Check port forward rule is configured correctly
3. Ensure no firewall blocking the host port
4. Test with `telnet 127.0.0.1 <host-port>`

**Cannot Reach VM:**

- For SSH: Use `ssh -p <port> user@127.0.0.1`
- For VNC: Use VNC client to connect to `127.0.0.1:<port>`
- For bridged: Use the VM's actual IP address on the network

---

## 8. Snapshot Errors

### Symptoms

- "Failed to create snapshot" error
- Snapshot list is empty
- Restore fails

### Solutions

**Snapshot Creation Fails:**

1. Verify `qemu-img` is installed and in PATH
2. Check disk path is correct and accessible
3. Ensure VM is not writing to disk (pause first for consistency)

**Snapshot List Empty:**

- Run **Refresh** in the Snapshots panel
- Verify the disk path is correct

**Restore Fails:**

- Ensure the VM is stopped before restoring
- Check you have write access to the disk image
- Verify the snapshot name is correct

---

## 9. GUI Problems

### Symptoms

- GUI doesn't start
- GUI crashes
- Panels don't load
- UI is unresponsive

### Solutions

**GUI Won't Start:**

1. Check Python and PyQt5 are installed:
   ```bash
   python -c "import PyQt5; print(PyQt5.__version__)"
   ```
2. Run with debug output:
   ```bash
   qemu-mcp gui --debug
   ```
3. Check for error messages in the terminal

**GUI Crashes:**

1. Check the crash log (if enabled)
2. Verify VM-Harness version is compatible with your system
3. Try running from source with `python -m vm_mcp.gui`

**Panels Not Loading:**

1. Restart the application
2. Check for error messages
3. Verify all dependencies are installed

---

## 10. Performance Issues

### Symptoms

- VM is slow
- High host CPU usage
- Guest responds slowly

### Solutions

**Improve VM Performance:**

1. Use hardware acceleration (WHPX or HAXM)
2. Allocate adequate RAM (minimum 2 GB for modern OS)
3. Use a qcow2 disk with appropriate size
4. Enable OpenGL if available for graphics acceleration
5. Reduce vCPU count if host is overloaded

**Check Resource Usage:**

- Use **Telemetry** panel for real-time metrics
- Use **Monitoring** panel for historical data
- Check host Task Manager/Activity Monitor

---

## 11. Debugging Tips

### Enable Debug Logging

Set log level to DEBUG in **Settings > Logging**:

```env
LOG_LEVEL=DEBUG
LOG_FILE=debug.log
```

### Check QEMU Command Line

Run QEMU manually to see the full command line:

```bash
# From VM-Harness, check what command would be executed
# Or run QEMU directly with your settings
qemu-system-x86_64 -machine q35 -m 8192 -smp 4 \
  -drive file=disk.qcow2,format=qcow2 \
  -display sdl -qmp tcp:127.0.0.1:4444,server,nowait
```

### Use QMP Console

Send manual QMP commands to diagnose:

```json
{
  "execute": "query-status"
}
```

```json
{
  "execute": "query-commands"
}
```

### Check System Resources

```bash
# Windows Task Manager or
tasklist /FI "IMAGENAME eq qemu*"

# Check disk space
dir

# Check memory usage
systeminfo | findstr /C:"Total Physical Memory"
```

### Collect Diagnostic Information

When reporting issues, include:

1. VM-Harness version
2. Python version (`python --version`)
3. QEMU version (`qemu-system-x86_64 --version`)
4. Operating system and version
5. Relevant error messages
6. QEMU command line being used
7. `.env` settings (remove sensitive values)

---

## Quick Reference: Common Error Messages

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| "QEMU binary not found" | Wrong path or QEMU not installed | Fix path in Settings or install QEMU |
| "Connection refused" (SSH) | SSH server not running in guest | Install SSH server in guest |
| "QMP disconnected" | QMP socket unavailable | Restart VM, check QMP settings |
| "Could not set up host forwarding" | Port conflict | Use different SSH port |
| "VM not running" | VM is stopped | Start the VM first |
| "Disk not found" | Wrong disk path | Update disk path in Settings |
| "Display initialization failed" | Display backend issue | Try different display type |

---

*Last updated: September 2026*
