from __future__ import annotations

import os
import sys
from pathlib import Path

from transport_overlay.autostart import configure_autostart_on_startup
from transport_overlay.config import load_config
from transport_overlay.instance import SingleInstance
from transport_overlay.poller import BusPoller
from transport_overlay.ui import BusOverlay, TrayController
from PySide6.QtWidgets import QApplication


def configure_stdio_logs() -> None:
    force_logs = os.environ.get("TRANSPORT_OVERLAY_LOGS") == "1"
    if not force_logs and sys.stderr is not None and sys.stderr.isatty():
        return

    base = os.environ.get("APPDATA")
    if base:
        log_dir = Path(base) / "TransportationOverlay" / "logs"
    else:
        log_dir = Path.home() / "AppData" / "Roaming" / "TransportationOverlay" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    sys.stdout = (log_dir / "launch-output.log").open("a", encoding="utf-8", buffering=1)
    sys.stderr = (log_dir / "launch-error.log").open("a", encoding="utf-8", buffering=1)


def main() -> int:
    configure_stdio_logs()

    instance = SingleInstance.acquire_or_restart_existing()
    if instance is None:
        print("Another Transportation Overlay instance is still running.", file=sys.stderr)
        return 1

    try:
        config = load_config()
    except Exception as error:
        print(f"Config error: {error}", file=sys.stderr)
        return 2

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    user_settings = configure_autostart_on_startup()
    overlay = BusOverlay(config)
    tray = TrayController(app, overlay, config, user_settings)
    poller = BusPoller(config)

    poller.snapshot_ready.connect(overlay.show_snapshot)
    poller.traffic_ready.connect(overlay.show_traffic)
    poller.snapshot_ready.connect(tray.update_snapshot)
    poller.error_ready.connect(overlay.show_error)
    poller.error_ready.connect(tray.update_error)
    poller.visibility_changed.connect(overlay.set_overlay_visible)
    poller.status_ready.connect(tray.update_status)
    poller.manual_tracking_changed.connect(tray.update_manual_tracking)
    tray.manual_tracking_requested.connect(poller.toggle_manual_tracking)

    app.aboutToQuit.connect(poller.stop)
    poller.start()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
