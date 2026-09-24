# Known Limitations

This document lists environment-specific gaps that are **not code defects** — the VM-Harness server and GUI are fully functional, but certain end-to-end scenarios require guest-side or host-side configuration that this environment does not provide.

---

## SSH in guest VM (E2E test skipped: 1/54)

**Symptom:** `tests/test_e2e_qmp_ssh.py::test_ssh_run_command` is skipped with reason "No SSH server in guest VM".

**Root cause:** The Omarchy guest VM does not run an SSH server (neither `sshd` nor `dropbear`). The QEMU user-mode NAT forwarding on port 2222 is active (QEMU listens and forwards), but there is no daemon inside the guest to accept connections on port 22.

**Why it can't be fixed in this environment:**

- **No console access:** QEMU is launched with `-display none` and no VNC/SPICE configured. The only interaction channels are QMP (control, no shell) and SSH forwarding (no daemon). The `-chardev socket` + `-device isa-serial` + `-append "console=ttyS0"` approach was attempted but `-append` requires `-kernel` (the VM boots from a disk image, not a kernel + initrd), so the serial console is not reachable.
- **No disk mounting tools:** The host does not have `libguestfs`/`guestfish` or `qemu-nbd` installed, so the qcow2 disk cannot be mounted and chrooted to install dropbear offline.
- **Raw disk scan confirmed:** Searching the raw qcow2 for `sshd` ELF signatures and path strings returned no matches (only coincidental byte sequences in compressed clusters). The guest OS image genuinely lacks an SSH server.

**SSH tools are still functional:** The 5 SSH MCP tools (`guest_exec`, `guest_file_read`, `guest_file_write`, `guest_file_list`, `guest_file_remove`) and the SSH bridge all work correctly at the unit level. The SSH E2E test is skipped solely because there is no server to connect to.

**To enable SSH E2E testing on a different host:** Install `dropbear` or `openssh-server` inside the guest OS by any available means (console, mounted disk, cloud-init), then the test will pass without any code changes.

---

## Port 2222 conflicts on Windows

**Symptom:** QEMU launches with `-netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22` fail with "Could not set up host forwarding rule" when another process is already listening on port 2222.

**Root cause:** Windows sometimes leaves stale listeners on port 2222 after QEMU exits (zombie processes, lingering NAT forwarders). The E2E test settings fixture uses port 2222 for SSH forwarding, which conflicts when the port is occupied.

**Workaround:** The test environment uses port 2223 instead (configurable via `SSH_PORT` in `.env`). Port 2223 does not conflict.

**To fix on a different host:** Ensure no other process binds port 2222 before launching QEMU, or use a different SSH forwarding port.

---

## Serial console not available

**Symptom:** Attempts to add `-chardev socket,id=serial0,path='\\.\pipe\OmarchySerial' -device isa-serial,id=serial0,chardev=serial0 -append "console=ttyS0"` to the QEMU command line fail because `-append` requires `-kernel`.

**Root cause:** The VM is configured to boot from a qcow2 disk (`-drive file=...,boot c`), not from a Linux kernel + initrd. The `-append` flag only works with `-kernel`.

**Impact:** No serial console access to the guest OS, which blocks interactive guest configuration (installing packages, debugging boot issues, etc.).

**To enable on a different host:** Either boot from a kernel+initrd with `-kernel` + `-append`, or configure the guest's GRUB to use a serial console and connect via a named pipe or Unix socket.

---

## PyInstaller distribution not built

**Symptom:** No standalone `.exe` distribution exists.

**Status:** PyInstaller 6.22.2 is installed in the Hermes venv but no build has been run. This is a future task, not a current gap.

---

## Multi-VM profiles not implemented

**Symptom:** The server can only control a single predefined VM (the one in `.env`).

**Status:** The MCP server uses a single `VmMCPSettings` instance. Multi-VM support (multiple disks, multiple QMP sockets, profile selection) is an architectural extension not yet started.

---

## Windows-only testing

**Symptom:** All tests run on Windows 10 with WHPX acceleration.

**Status:** The code is written to be cross-platform (Unix socket paths, POSIX paths in settings), but no Linux/macOS testing has been done. The `test_qmp_uri_unix` test is skipped on Windows with an explicit `skipTest("Unix sockets not supported on Windows")`.
