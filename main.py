from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from transport_overlay.config import load_config
from transport_overlay.poller import BusPoller
from transport_overlay.ui import BusOverlay, TrayController


def main() -> int:
    try:
        config = load_config()
    except Exception as error:
        print(f"Config error: {error}", file=sys.stderr)
        return 2

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = BusOverlay(config)
    tray = TrayController(app, overlay, config)
    poller = BusPoller(config)

    poller.snapshot_ready.connect(overlay.show_snapshot)
    poller.snapshot_ready.connect(tray.update_snapshot)
    poller.error_ready.connect(overlay.show_error)
    poller.error_ready.connect(tray.update_error)
    poller.visibility_changed.connect(overlay.set_overlay_visible)
    poller.status_ready.connect(tray.update_status)

    app.aboutToQuit.connect(poller.stop)
    poller.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
