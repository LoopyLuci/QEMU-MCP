# PyQt5 GUI Scaling Gap Analysis Report
## Project: QEMU-MCP (`C:/Projects/QEMU-MCP/gui/`)

### Summary
The application has **no High-DPI scaling awareness**, meaning fonts, widgets, and layouts render at native pixel sizes. On a 4K display (3840×2160 at 200% DPI scaling), the entire GUI will appear tiny and unusable without system-level DPI virtualization.

---

## 🔴 CRITICAL GAPS

### 1. No High-DPI Scaling Enabled
**File:** `gui/__main__.py` (line 76), `gui/main_window.py` (line 666)
- `QApplication` is created without setting `Qt.AA_EnableHighDpiScaling` or `Qt.AA_UseHighDpiPixmaps`
- No `QApplication.setAttribute()` call anywhere in the codebase
- Without this, Qt uses 1:1 pixel mapping — on a 4K display the window will be half the expected size
- **Fix:** Add `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)` before `QApplication(sys.argv)`

### 2. All Font Sizes Are Hardcoded Pixels
**Files:** All panel files, `gui/theme.py`, `gui/widgets.py`
- Design tokens define font sizes in pixel values: `FS_XS=10, FS_SM=11, FS_MD=12, FS_LG=13, FS_XL=14, FS_XXL=16`
- These are injected into stylesheets as `font-size: 12px;` etc.
- **Every** stylesheet string uses `str(T.FS_MD) + "px"` pattern — none are DPI-relative
- Direct `QFont("Consolas", 10)` calls in code (`panels_chat.py:218`, `panels_qmp_console.py:45`)
- `QFont("Arial", 12, QFont.Bold)` in tray icon painter (`main_window.py:399`)
- **Fix:** Use point sizes (`pt`) instead of pixels (`px`) for font-size in QSS, or multiply by `devicePixelRatioF()`

---

## 🔴 MAJOR GAPS

### 3. Sidebar Has Fixed Width
**File:** `gui/main_window.py:196`
- `self.setFixedWidth(180)` on Sidebar — on 4K this looks cramped
- Sidebar button height: `btn.setFixedHeight(40)` (line 212)
- Window control buttons: `setFixedSize(T.MD * 3, T.LG * 2)` = 36×32 px (lines 119, 126, 133)
- **Fix:** Use `setMinimumWidth()` with a DPI-aware calculation, or use `setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)`

### 4. Title Bar Has Fixed Height
**File:** `gui/main_window.py:76`
- `self.setFixedHeight(40)` — title bar won't scale
- Title label height: `title_label.setFixedHeight(24)` (line 99)
- **Fix:** Use `setMinimumHeight()` with DPI-aware calculation

### 5. Settings Panel — Extensive Fixed Widths
**File:** `gui/panels_settings.py`
- `setFixedWidth(360)` on ~10 input fields (qemu_bin, qemu_args, disk, iso, log_file)
- `setFixedWidth(200)` on vm_name, hostname, ssh_host, guest_user inputs
- `setFixedWidth(120)` on ram_spin, cpu_spin, ssh_port_spin
- `setFixedWidth(100)` on ~12 labels (bin_label, args_label, name_label, etc.)
- `setFixedWidth(140)` on display_combo, accel_mode_combo, auth_method_combo
- **All use QHBoxLayout with addStretch()** — but fixed-width inputs prevent the stretch from expanding the input fields themselves
- **Fix:** Remove `setFixedWidth()` from inputs; use `setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)` and let the layout handle widths

### 6. No QScrollArea for Panel Content
**Files:** All panel files
- Most panels use plain `QVBoxLayout` without wrapping in `QScrollArea`
- If window height is reduced below content height, panels clip instead of scroll
- `panels_chat.py` imports `QScrollArea` but never uses it
- **Fix:** Wrap panel content in `QScrollArea` with `setWidgetResizable(True)` for scrollable panels

### 7. Hundreds of Fixed-Size Buttons Across All Panels
**Count:** 100+ `setFixedSize()` calls on QPushButton widgets alone
- `panels.py:112-134` — start/stop/reset: `setFixedSize(140, 40)`
- `panels_iso.py:91-264` — 8 buttons with `setFixedSize(90-160, 32)`
- `panels_snapshots.py:56-86` — 4 buttons `setFixedSize(90, 32)`
- `panels_storage.py:58-98` — 5 buttons `setFixedSize(110, 32)`
- `panels_monitoring.py:112-172` — add/del/refresh/export: `setFixedSize(100, 32)`
- `panels_qmp_console.py:75,115,131` — preset buttons `setFixedSize(90, 28)`
- `panels_usb.py:447-582` — clear/refresh/attach/detach: various fixed sizes
- **Fix:** Replace `setFixedSize()` with `setMinimumSize()` or `setMinimumHeight()` to allow button growth on 4K

### 8. Fixed Card Heights
**Files:** Multiple
- `panels.py:42` — `status_card.setFixedHeight(180)`
- `panels.py:157` — `activity_list.setMaximumHeight(150)`
- `panels_vm_control.py:55` — `context_card.setFixedHeight(60)`
- `panels_multi_vm_dashboard.py:42` — `VMCard.setFixedHeight(120)`
- `panels_multi_vm_dashboard.py:198` — `resource_card.setFixedHeight(100)`
- `panels_multi_vm_dashboard.py:265` — `active_vm_card.setFixedHeight(60)`
- `panels_security.py:235,396` — stats_card (40), add_card (50)
- **Fix:** Replace `setFixedHeight()` with `setMinimumHeight()` where content-driven sizing is appropriate

---

## 🟡 MODERATE GAPS

### 9. QR Code Label Fixed Size
**File:** `gui/panels_pairing.py:116`
- `self.qr_label.setFixedSize(200, 200)` — QR code renders at fixed 200×200 pixels
- On 4K this will appear very small
- **Fix:** Use `setMinimumSize()` and scale QR generation to widget size

### 10. Wizard Header Font Hardcoded
**File:** `gui/panels_wizard.py:54`
- `header.setStyleSheet("... font-size: 18px; ...")` — hardcoded in inline stylesheet
- **Fix:** Use `T.FS_XXL` token or larger relative sizing

### 11. Toast Notification Fixed Width
**File:** `gui/widgets.py:161`
- `self.setFixedWidth(320)` — won't scale to wider windows
- **Fix:** Use `setMinimumWidth()` and `setMaximumWidth()` with proportions

### 12. IconButton Fixed Size
**File:** `gui/widgets.py:78` (StatusIndicator), `gui/widgets.py:279` (StatCard)
- `StatusIndicator.setFixedSize(12, 12)` — tiny dot on 4K
- `StatCard.setFixedHeight(32)` — compact stat card fixed
- **Fix:** Use DPI-aware size calculations

### 13. No resizeEvent Overrides
**Files:** All panel files
- No panel implements `resizeEvent()` to adjust layout, font sizes, or widget visibility on resize
- `TopologyDiagram` (`panels_network_editor.py:95`) does implement `paintEvent()` but uses hardcoded pixel coordinates for drawing
- **Fix:** Implement `resizeEvent()` on panels that need dynamic re-layout (diagrams, charts, multi-column grids)

### 14. Topology Diagram Uses Hardcoded Coordinates
**File:** `panels_network_editor.py:115-196`
- All drawing coordinates are hardcoded pixel values (60, 50, 120, etc.)
- `painter.drawRoundedRect(host_x, host_y, host_w, host_h, 8, 8)` — won't scale with widget size
- **Fix:** Calculate positions as fractions of `self.width()` and `self.height()`

### 15. FileTree Fixed Width
**File:** `gui/widgets.py:161` (Toast), `gui/panels_guest_terminal.py:219-220`
- `self.setMinimumWidth(280)` and `setMaximumWidth(400)` on file tree
- **Fix:** Allow wider expansion on 4K

---

## 🟢 MINOR GAPS

### 16. Minimum Window Size May Be Insufficient
**File:** `gui/main_window.py:263`
- `self.setMinimumSize(1200, 800)` — reasonable for 1080p, could be scaled for 4K

### 17. No SizePolicy Set on Most Widgets
- Most widgets use default `QSizePolicy.Preferred` rather than `Expanding`
- `panels.py` and others don't set `sizePolicy` on cards, lists, or input widgets
- **Fix:** Set `QSizePolicy.Expanding` on widgets that should grow horizontally

### 18. Missing addStretch() in Some Panels
- Not all panels have `layout.addStretch()` at the bottom
- This causes widgets to cluster at the top with wasted space below on larger windows
- **Fix:** Ensure all main panel layouts end with `addStretch()`

### 19. LogEntry and Timeline Fixed Heights
**File:** `gui/widgets.py:716, 844`
- `LogEntry.setFixedHeight(22)`
- `ProgressBar.setFixedHeight(4)`
- **Fix:** Use `setMinimumHeight()` or DPI-aware values

---

## 📋 RECOMMENDED FIX PRIORITY

1. **Enable High-DPI scaling** (`__main__.py`) — single-line fix, massive impact
2. **Convert font-size px→pt** in `theme.py` — changes all font rendering to DPI-aware
3. **Remove setFixedWidth()** from Settings panel inputs — allows proper horizontal stretch
4. **Wrap panels in QScrollArea** — enables vertical scrolling when needed
5. **Replace setFixedHeight() with setMinimumHeight()** on cards
6. **Scale button sizes** for 4K (use `setMinimumSize()` instead of `setFixedSize()`)
7. **Fix TopologyDiagram** coordinate calculation
8. **Implement resizeEvent()** for dynamic panels
9. **Add DPI detection** and scale minimum window size accordingly
