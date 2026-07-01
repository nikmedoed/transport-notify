from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from datetime import time
from pathlib import Path


CONFIG_PATH = Path("config.toml")
DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ScheduleConfig:
    enabled: bool
    active_from: time
    active_to: time
    poll_seconds: int
    inactive_check_seconds: int


@dataclass(frozen=True)
class YandexConfig:
    stop_ids: tuple[str, ...]
    routes: tuple[str, ...]
    arrivals_per_route: int
    user_agent: str
    debug_dump_path: Path
    stop_page_url_template: str


@dataclass(frozen=True)
class AppConfig:
    title: str
    schedule: ScheduleConfig
    yandex: YandexConfig


class ConfigError(RuntimeError):
    pass


def default_config_paths() -> tuple[Path, ...]:
    paths = [CONFIG_PATH]
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve().parent / CONFIG_PATH)
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            paths.append(Path(bundle_dir) / CONFIG_PATH)
    return tuple(dict.fromkeys(paths))


def resolve_config_path(path: Path = CONFIG_PATH) -> Path:
    if path != CONFIG_PATH:
        return path

    for candidate in default_config_paths():
        if candidate.exists():
            return candidate
    return path


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    path = resolve_config_path(path)
    if not path.exists():
        checked = ", ".join(str(item.resolve()) for item in default_config_paths())
        raise ConfigError(f"Не найден конфиг. Проверенные пути: {checked}")

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    app = raw.get("app", {})
    schedule = raw.get("schedule", {})
    yandex = raw.get("yandex", {})

    return AppConfig(
        title=str(app.get("title", "Транспорт")),
        schedule=ScheduleConfig(
            enabled=bool(schedule.get("enabled", False)),
            active_from=parse_hhmm(str(schedule.get("active_from", "18:30"))),
            active_to=parse_hhmm(str(schedule.get("active_to", "21:00"))),
            poll_seconds=max(10, int(schedule.get("poll_seconds", 45))),
            inactive_check_seconds=max(60, int(schedule.get("inactive_check_seconds", 300))),
        ),
        yandex=YandexConfig(
            stop_ids=tuple(str(item) for item in yandex.get("stop_ids", [])),
            routes=tuple(str(item) for item in yandex.get("routes", [])),
            arrivals_per_route=max(1, int(yandex.get("arrivals_per_route", 3))),
            user_agent=str(yandex.get("user_agent", DEFAULT_BROWSER_USER_AGENT)),
            debug_dump_path=Path(str(yandex.get("debug_dump_path", "last_yandex_reply.json"))),
            stop_page_url_template=str(
                yandex.get(
                    "stop_page_url_template",
                    "https://yandex.com/maps/10262/yerevan/stops/{stop_id}/",
                )
            ),
        ),
    )


def parse_hhmm(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    except ValueError as error:
        raise ConfigError(f"Время должно быть в формате HH:MM, получено: {value}") from error
