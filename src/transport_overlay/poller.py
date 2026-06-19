from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from transport_overlay.config import AppConfig
from transport_overlay.models import ArrivalSnapshot
from transport_overlay.schedule import is_active_now, seconds_until_active
from transport_overlay.yandex_live import fetch_yandex_snapshot


class BusPoller(QObject):
    snapshot_ready = Signal(object)
    error_ready = Signal(str)
    visibility_changed = Signal(bool)
    status_ready = Signal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._stop_event = threading.Event()
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

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            if not is_active_now(self.config.schedule):
                self.visibility_changed.emit(False)
                sleep_seconds = seconds_until_active(self.config.schedule)
                self.status_ready.emit(f"Сплю до периода показа, проверка через {sleep_seconds} сек.")
                await self._sleep(sleep_seconds)
                continue

            await self._poll_once()
            await self._sleep(self.config.schedule.poll_seconds)

    async def _poll_once(self) -> None:
        try:
            snapshot = await self.fetch_snapshot()
            self.snapshot_ready.emit(snapshot)
        except Exception as error:
            self.error_ready.emit(str(error))

    async def _sleep(self, seconds: int) -> None:
        deadline = datetime.now() + timedelta(seconds=seconds)
        while not self._stop_event.is_set() and datetime.now() < deadline:
            await asyncio.sleep(min(1, max(0, (deadline - datetime.now()).total_seconds())))

    async def fetch_snapshot(self) -> ArrivalSnapshot:
        return await asyncio.to_thread(fetch_yandex_snapshot, self.config.yandex)
