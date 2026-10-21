from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TrafficReading:
    name: str
    level: str | None = None
    error: str | None = None

    @property
    def score(self) -> int | None:
        return {"green": 1, "yellow": 4, "orange": 7, "red": 9, "darkred": 10}.get(self.level)


@dataclass(frozen=True)
class TrafficSnapshot:
    readings: tuple[TrafficReading, ...]
    updated_at: datetime

    @property
    def average(self) -> float | None:
        scores = [reading.score for reading in self.readings]
        if not scores or any(score is None for score in scores):
            return None
        return sum(scores) / len(scores)


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
