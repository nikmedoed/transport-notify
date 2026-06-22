from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from transport_overlay.config import AppConfig
from transport_overlay.formatting import arrival_label
from transport_overlay.models import Arrival, ArrivalSnapshot


CORNER_MARGIN_BOTTOM = 2
CORNER_MARGIN_LEFT = 2
BACKGROUND_ALPHA = 142
ROW_HEIGHT = 17


class RouteRow(QFrame):
    def __init__(self, route: str, arrivals: tuple[Arrival, ...]) -> None:
        super().__init__()
        self.setObjectName("routeRow")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(ROW_HEIGHT)

        route_label = QLabel(route)
        route_label.setObjectName("routeNumber")
        route_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        route_label.setFixedSize(21, ROW_HEIGHT)

        separator_label = QLabel(":")
        separator_label.setObjectName("separator")
        separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator_label.setFixedSize(4, ROW_HEIGHT)

        times_layout = QHBoxLayout()
        times_layout.setContentsMargins(3, 0, 0, 0)
        times_layout.setSpacing(0)
        add_time_labels(times_layout, arrivals)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(route_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(separator_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(times_layout)


def add_time_labels(layout: QHBoxLayout, arrivals: tuple[Arrival, ...]) -> None:
    if not arrivals:
        label = QLabel("-")
        label.setObjectName("mutedTime")
        label.setFixedHeight(ROW_HEIGHT)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)
        return

    for index, arrival in enumerate(arrivals):
        if index > 0:
            comma = QLabel(", ")
            comma.setObjectName("comma")
            comma.setFixedHeight(ROW_HEIGHT)
            comma.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(comma)

        label = QLabel(arrival_label(arrival))
        if index == 0:
            label.setObjectName("nearestTime")
        else:
            label.setObjectName("time")
        label.setFixedHeight(ROW_HEIGHT)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)


class BusOverlay(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.route_rows: list[RouteRow] = []
        self.anchor_screen = QApplication.primaryScreen()

        self.setWindowTitle(config.title)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.shell = QFrame()
        self.shell.setObjectName("shell")

        self.routes_layout = QVBoxLayout()
        self.routes_layout.setContentsMargins(0, 0, 0, 0)
        self.routes_layout.setSpacing(1)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(2, 0, 2, 5)
        shell_layout.setSpacing(0)
        shell_layout.addLayout(self.routes_layout)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.shell)

        self.setStyleSheet(self._stylesheet())
        self.hide()

    def show_snapshot(self, snapshot: ArrivalSnapshot) -> None:
        self._clear_routes()
        for route in sorted(snapshot.routes, key=route_sort_key):
            row = RouteRow(route.route, route.arrivals)
            self.routes_layout.addWidget(row)
            self.route_rows.append(row)

        self._show_anchored()

    def show_error(self, message: str) -> None:
        self._clear_routes()

        label = QLabel(message)
        label.setObjectName("emptyLabel")
        label.setWordWrap(True)
        self.routes_layout.addWidget(label)

        self._show_anchored()

    def set_overlay_visible(self, visible: bool) -> None:
        if visible:
            self._show_anchored()
        else:
            self.hide()

    def _show_anchored(self) -> None:
        self._refresh_layout_size()
        self.show()
        self._place_bottom_left()
        self.raise_()
        QTimer.singleShot(0, self._place_bottom_left)

    def _clear_routes(self) -> None:
        while self.routes_layout.count():
            item = self.routes_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.route_rows.clear()

    def _refresh_layout_size(self) -> None:
        self.routes_layout.invalidate()
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()

    def _place_bottom_left(self) -> None:
        screen = self._anchor_screen()
        if screen is None:
            return

        self._refresh_layout_size()
        x, y = self._bottom_left_position(screen, self.size())
        self.move(QPoint(x, y))

    def _bottom_left_position(self, screen, size: QSize) -> tuple[int, int]:
        area = screen.geometry()
        x = area.left() + CORNER_MARGIN_LEFT
        y = area.bottom() - size.height() - CORNER_MARGIN_BOTTOM + 1

        x = max(area.left(), min(x, area.right() - size.width() + 1))
        y = max(area.top(), min(y, area.bottom() - size.height() + 1))
        return x, y

    def _anchor_screen(self):
        screens = QApplication.screens()
        if self.anchor_screen in screens:
            return self.anchor_screen

        self.anchor_screen = QApplication.primaryScreen()
        return self.anchor_screen

    def _stylesheet(self) -> str:
        return f"""
        #shell {{
            background-color: rgba(20, 22, 24, {BACKGROUND_ALPHA});
            border: 1px solid rgba(255, 255, 255, 18);
            border-radius: 5px;
        }}
        #routeNumber {{
            color: rgba(255, 255, 255, 215);
            font: 900 13px "Segoe UI";
            background: transparent;
        }}
        #separator {{
            color: rgba(255, 255, 255, 155);
            font: 800 12px "Segoe UI";
            background: transparent;
        }}
        #nearestTime {{
            color: #2dd4bf;
            font: 900 12px "Segoe UI";
            background: transparent;
        }}
        #time {{
            color: rgba(255, 255, 255, 210);
            font: 800 12px "Segoe UI";
            background: transparent;
        }}
        #comma {{
            color: rgba(255, 255, 255, 135);
            font: 800 12px "Segoe UI";
            background: transparent;
        }}
        #mutedTime {{
            color: rgba(255, 255, 255, 100);
            font: 800 12px "Segoe UI";
            background: transparent;
        }}
        """


def route_sort_key(route) -> tuple[int, str]:
    if not route.arrivals:
        return (sys.maxsize, route.route)

    first = route.arrivals[0]
    if first.timestamp is None:
        return (sys.maxsize - 1, route.route)

    return (first.timestamp, route.route)
