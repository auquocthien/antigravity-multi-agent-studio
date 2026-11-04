"""Application entrypoint for the Linux-native desktop utility."""

import os
import sys
import signal
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


def setup_posix_signals(app: QApplication) -> None:
    """Configure POSIX signal handlers to allow clean Ctrl+C termination from Linux terminal."""
    # Let Python handle SIGINT / SIGTERM periodically via a QTimer tick
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())

    timer = QTimer()
    timer.timeout.connect(lambda: None)  # Allow Python interpreter to process signals
    timer.start(500)
    # Keep reference on app to prevent garbage collection
    setattr(app, "_sigint_timer", timer)


def main() -> int:
    """Main application lifecycle runner."""
    # Enforce Wayland/X11 high-DPI scaling
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("LinuxNativeUtility")
    app.setOrganizationName("Antigravity")

    # Set application icon if present
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "assets", "app.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    setup_posix_signals(app)

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))

    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
