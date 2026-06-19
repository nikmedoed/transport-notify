from __future__ import annotations

import math
from datetime import datetime

from transport_overlay.models import Arrival, ArrivalSnapshot


def arrival_label(arrival: Arrival, now: datetime | None = None) -> str:
    now = now or datetime.now()

    if arrival.timestamp is None:
        return arrival.text or "?"

    arrival_time = datetime.fromtimestamp(arrival.timestamp)
    minutes = math.ceil((arrival_time - now).total_seconds() / 60)

    if minutes <= 0:
        return "0"
    if minutes <= 90:
        return str(minutes)
    return arrival_time.strftime("%H:%M")


def tray_label(snapshot: ArrivalSnapshot | None) -> str:
    if snapshot is None or snapshot.nearest is None:
        return ""

    nearest = snapshot.nearest
    if nearest.timestamp is None:
        return nearest.text[:2]

    minutes = math.ceil((datetime.fromtimestamp(nearest.timestamp) - datetime.now()).total_seconds() / 60)
    if minutes <= 0:
        return "0"
    if minutes <= 99:
        return str(minutes)
    return datetime.fromtimestamp(nearest.timestamp).strftime("%H")
