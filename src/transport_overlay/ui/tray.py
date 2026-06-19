from __future__ import annotations

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from transport_overlay.config import AppConfig
from transport_overlay.formatting import arrival_label, tray_label
from transport_overlay.models import ArrivalSnapshot
from transport_overlay.ui.overlay import BusOverlay


class TrayController(QObject):
    def __init__(self, app: QApplication, overlay: BusOverlay, config: AppConfig) -> None:
        super().__init__()
        self.app = app
        self.overlay = overlay
        self.config = config
        self.last_snapshot: ArrivalSnapshot | None = None

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(make_tray_icon(None))
        self.tray.setToolTip(config.title)

        menu = QMenu()
        self.toggle_action = menu.addAction("Показать / скрыть")
        self.toggle_action.triggered.connect(self.toggle_overlay)
        quit_action = menu.addAction("Выход")
        quit_action.triggered.connect(app.quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def update_snapshot(self, snapshot: ArrivalSnapshot) -> None:
        self.last_snapshot = snapshot
        self.tray.setIcon(make_tray_icon(tray_label(snapshot)))
        self.tray.setToolTip(self._tooltip(snapshot))

    def update_error(self, message: str) -> None:
        self.tray.setIcon(make_tray_icon("!"))
        self.tray.setToolTip(f"{self.config.title}\nОшибка: {message}")

    def update_status(self, message: str) -> None:
        if self.last_snapshot is None:
            self.tray.setToolTip(f"{self.config.title}\n{message}")

    def toggle_overlay(self) -> None:
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.set_overlay_visible(True)

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_overlay()

    def _tooltip(self, snapshot: ArrivalSnapshot) -> str:
        lines = [self.config.title]

        nearest = snapshot.nearest
        for route in snapshot.routes:
            values = ", ".join(arrival_label(arrival) for arrival in route.arrivals) or "нет данных"
            prefix = ">" if nearest is not None and nearest in route.arrivals else " "
            lines.append(f"{prefix} {route.route}: {values}")

        lines.append(f"Обновлено: {snapshot.updated_at:%H:%M:%S}")
        return "\n".join(lines)


def make_tray_icon(text: str | None = None) -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    cyan = QColor(45, 212, 191)
    dark = QColor(3, 16, 18)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(cyan)
    painter.drawRoundedRect(26, 26, 204, 204, 46, 46)

    if text:
        painter.setPen(dark)
        font_size = 118 if len(text) <= 2 else 88
        painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Black))
        painter.drawText(QRect(20, 28, 216, 196), Qt.AlignmentFlag.AlignCenter, text[:3])

    painter.end()

    return QIcon(pixmap)
