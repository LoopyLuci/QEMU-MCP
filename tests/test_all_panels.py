"""Instantiate every GUI panel with offscreen rendering and report failures."""

from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PyQt5.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    failures: list[tuple[str, str]] = []
    successes: list[str] = []

    # Build the panel list — mirrors gui/main_window.py panel registration.
    try:
        from gui.main_window import MainWindow
    except Exception:
        failures.append(("MainWindow import", traceback.format_exc()))
        print("MAIN_WINDOW_IMPORT_FAILED")
        return 1

    window = MainWindow()
    panel_names = list(window.panels.keys())
    for name in panel_names:
        try:
            panel = window.panels[name]
            if panel is None:
                failures.append((name, "Panel is None after construction"))
                continue
            # Exercise basic repaint paths.
            panel.hide()
            panel.show()
            successes.append(name)
        except Exception:
            failures.append((name, traceback.format_exc()))

    # Test sparkline widget separately since it is custom.
    try:
        from gui.panels_container_stats import SparklineWidget
        from PyQt5.QtGui import QColor
        spark = SparklineWidget(QColor("#60a5fa"))
        for i in range(20):
            spark.add_value(float(i))
        spark.repaint()
        successes.append("SparklineWidget")
    except Exception:
        failures.append(("SparklineWidget", traceback.format_exc()))

    window.close()
    window.deleteLater()

    print(f"INSTANTIATED {len(successes)} PANELS:")
    for name in successes:
        print(f"  [OK] {name}")
    if failures:
        print(f"FAILED {len(failures)} PANELS:")
        for name, error in failures:
            print(f"  [FAIL] {name}")
            print(error)
        return 1
    print("ALL_PANELS_INSTANTIATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
