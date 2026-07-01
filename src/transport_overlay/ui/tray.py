from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from transport_overlay.config import AppConfig
from transport_overlay.formatting import arrival_label, tray_label
from transport_overlay.models import ArrivalSnapshot
from transport_overlay.ui.overlay import BusOverlay


class TrayController(QObject):
    manual_tracking_requested = Signal()

    def __init__(self, app: QApplication, overlay: BusOverlay, config: AppConfig) -> None:
        super().__init__()
        self.app = app
        self.overlay = overlay
        self.config = config
        self.last_snapshot: ArrivalSnapshot | None = None

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(make_tray_icon(None))
        self.tray.setToolTip(config.title)

        self.menu = QMenu()
        self.manual_tracking_action = self.menu.addAction("Отслеживать сейчас")
        self.manual_tracking_action.setCheckable(True)
        self.manual_tracking_action.triggered.connect(lambda _checked=False: self._request_manual_tracking())
        quit_action = self.menu.addAction("Выход")
        quit_action.triggered.connect(app.quit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def update_snapshot(self, snapshot: ArrivalSnapshot) -> None:
        self.last_snapshot = snapshot
        self.tray.setIcon(make_tray_icon(tray_label(snapshot)))
        self.tray.setToolTip(self._tooltip(snapshot))

    def update_error(self, message: str) -> None:
        self.last_snapshot = None
        self.tray.setIcon(make_tray_icon("!"))
        self.tray.setToolTip(f"{self.config.title}\nОшибка: {message}")

    def update_status(self, message: str) -> None:
        icon_text = "ON" if self.manual_tracking_action.isChecked() else "II"
        self.tray.setIcon(make_tray_icon(icon_text))
        self.tray.setToolTip(f"{self.config.title}\n{message}")

    def update_manual_tracking(self, enabled: bool) -> None:
        self.manual_tracking_action.setChecked(enabled)
        self.manual_tracking_action.setText(
            "Отключить отслеживание" if enabled else "Отслеживать сейчас"
        )
        if enabled:
            self.tray.setIcon(make_tray_icon("ON"))
            self.tray.setToolTip(f"{self.config.title}\nРучное отслеживание включено.")

    def _request_manual_tracking(self) -> None:
        self.manual_tracking_requested.emit()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            self._request_manual_tracking()

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
    badge_rect = QRectF(26, 26, 204, 204)
    painter.drawRoundedRect(badge_rect, 46, 46)

    if text:
        text = text[:3]
        painter.setPen(dark)
        font_size = 118 if len(text) <= 2 else 88
        font = QFont("Segoe UI", font_size, QFont.Weight.Black)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_rect = QRectF(metrics.tightBoundingRect(text))
        baseline = QPointF(
            badge_rect.center().x() - text_rect.center().x(),
            badge_rect.center().y() - text_rect.center().y(),
        )
        painter.drawText(baseline, text)

    painter.end()

    return QIcon(pixmap)
