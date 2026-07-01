from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from transport_overlay.config import AppConfig
from transport_overlay.models import ArrivalSnapshot
from transport_overlay.schedule import is_active_now, seconds_until_transition
from transport_overlay.yandex_live import fetch_yandex_snapshot


class BusPoller(QObject):
    snapshot_ready = Signal(object)
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
