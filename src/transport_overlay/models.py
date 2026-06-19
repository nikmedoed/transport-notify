from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Arrival:
    route: str
    text: str
    timestamp: int | None


@dataclass(frozen=True)
class RouteArrivals:
    route: str
    arrivals: tuple[Arrival, ...]


@dataclass(frozen=True)
class ArrivalSnapshot:
    stop_name: str
    routes: tuple[RouteArrivals, ...]
    updated_at: datetime

    @property
    def nearest(self) -> Arrival | None:
        candidates = [
            arrival
            for route in self.routes
            for arrival in route.arrivals
            if arrival.timestamp is not None
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda arrival: arrival.timestamp or 0)
