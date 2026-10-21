from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from transport_overlay.config import AppConfig
from transport_overlay.models import ArrivalSnapshot, TrafficReading, TrafficSnapshot
from transport_overlay.schedule import is_active_now, seconds_until_transition
from transport_overlay.yandex_live import fetch_yandex_snapshot
from transport_overlay.traffic import fetch_traffic_snapshot


class BusPoller(QObject):
    snapshot_ready = Signal(object)
    traffic_ready = Signal(object)
    error_ready = Signal(str)
    visibility_changed = Signal(bool)
    status_ready = Signal(str)
    manual_tracking_changed = Signal(bool)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._stop_event = threading.Event()
        self._tracking_enabled_event = threading.Event()
        self._wake_event = threading.Event()
        self._last_schedule_active = is_active_now(self.config.schedule)
        if self._last_schedule_active:
            self._tracking_enabled_event.set()
        self._thread: threading.Thread | None = None
        self._next_traffic_poll = 0.0

    def start(self) -> None:
        if self._thread is not None:
            return

        self._thread = threading.Thread(
            target=lambda: asyncio.run(self._run()),
            name="transport-poller",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def toggle_manual_tracking(self) -> None:
        self._set_tracking_enabled(
            not self._tracking_enabled_event.is_set(),
            "Ручное переключение",
            wake=True,
        )

    async def _run(self) -> None:
        self.manual_tracking_changed.emit(self._tracking_enabled_event.is_set())

        while not self._stop_event.is_set():
            self._apply_schedule_trigger()

            if not self._tracking_enabled_event.is_set():
                self.visibility_changed.emit(False)
                self._emit_paused_status()
                await self._sleep(seconds_until_transition(self.config.schedule))
                continue

            await self._poll_once()
            await self._sleep(self.config.schedule.poll_seconds)

    def _apply_schedule_trigger(self) -> None:
        schedule_active = is_active_now(self.config.schedule)
        if schedule_active == self._last_schedule_active:
            return

        self._last_schedule_active = schedule_active
        self._set_tracking_enabled(
            schedule_active,
            "Триггер расписания",
            wake=False,
        )

    def _set_tracking_enabled(self, enabled: bool, source: str, wake: bool) -> None:
        if enabled:
            self._next_traffic_poll = 0.0
            self._tracking_enabled_event.set()
        else:
            self._tracking_enabled_event.clear()

        if wake:
            self._wake_event.set()

        self.manual_tracking_changed.emit(enabled)

        if enabled:
            self.status_ready.emit(f"{source}: отслеживание включено.")
        else:
            self.visibility_changed.emit(False)
            self.status_ready.emit(f"{source}: отслеживание выключено.")

    def _emit_paused_status(self) -> None:
        self.status_ready.emit(
            f"Пауза до следующего триггера расписания. "
            "Фоновый процесс работает."
        )

    async def _poll_once(self) -> None:
        await asyncio.gather(self._poll_arrivals(), self._poll_traffic())

    async def _poll_traffic(self) -> None:
        if not self.config.traffic.enabled or time.monotonic() < self._next_traffic_poll:
            return
        try:
            snapshot = await asyncio.to_thread(fetch_traffic_snapshot, self.config.traffic)
        except Exception as error:
            snapshot = TrafficSnapshot(
                tuple(TrafficReading(point.name, error=str(error)) for point in self.config.traffic.points),
                datetime.now(),
            )
        self._next_traffic_poll = time.monotonic() + self.config.traffic.poll_seconds
        if self._tracking_enabled_event.is_set():
            self.traffic_ready.emit(snapshot)

    async def _poll_arrivals(self) -> None:
        try:
            snapshot = await self.fetch_snapshot()
            if not self._tracking_enabled_event.is_set():
                self.visibility_changed.emit(False)
                return
            self.snapshot_ready.emit(snapshot)
        except Exception as error:
            if not self._tracking_enabled_event.is_set():
                self.visibility_changed.emit(False)
                return
            self.error_ready.emit(str(error))

    async def _sleep(self, seconds: int) -> None:
        deadline = datetime.now() + timedelta(seconds=seconds)
        while (
            not self._stop_event.is_set()
            and not self._wake_event.is_set()
            and datetime.now() < deadline
        ):
            await asyncio.sleep(min(1, max(0, (deadline - datetime.now()).total_seconds())))
        self._wake_event.clear()

    async def fetch_snapshot(self) -> ArrivalSnapshot:
        return await asyncio.to_thread(fetch_yandex_snapshot, self.config.yandex)
