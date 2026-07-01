from __future__ import annotations

import math
from datetime import datetime, timedelta

from transport_overlay.config import ScheduleConfig


def is_active_now(config: ScheduleConfig, now: datetime | None = None) -> bool:
    if not config.enabled:
        return True

    now = now or datetime.now()
    current = now.time()

    if config.active_from <= config.active_to:
        return config.active_from <= current < config.active_to

    return current >= config.active_from or current < config.active_to


def seconds_until_active(config: ScheduleConfig, now: datetime | None = None) -> int:
    if not config.enabled or is_active_now(config, now):
        return 0

    now = now or datetime.now()
    start = datetime.combine(now.date(), config.active_from)
    if start <= now:
        start += timedelta(days=1)

    seconds = math.ceil((start - now).total_seconds())
    return max(1, min(seconds, config.inactive_check_seconds))


def seconds_until_transition(config: ScheduleConfig, now: datetime | None = None) -> int:
    if not config.enabled:
        return config.inactive_check_seconds

    now = now or datetime.now()
    candidates = [
        datetime.combine(now.date(), config.active_from),
        datetime.combine(now.date(), config.active_to),
    ]
    candidates.extend(candidate + timedelta(days=1) for candidate in tuple(candidates))

    upcoming = min(candidate for candidate in candidates if candidate > now)
    seconds = math.ceil((upcoming - now).total_seconds())
    return max(1, min(seconds, config.inactive_check_seconds))
