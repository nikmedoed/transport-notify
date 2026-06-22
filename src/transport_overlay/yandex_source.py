from __future__ import annotations

import json
import sys
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

from transport_overlay.config import YandexConfig
from transport_overlay.models import Arrival, ArrivalSnapshot, RouteArrivals


def parse_yandex_reply(config: YandexConfig, reply: dict[str, Any]) -> ArrivalSnapshot:
    data = extract_stop_data(reply)
    if not isinstance(data, dict):
        save_debug_reply(config, reply)
        raise ValueError(f"Яндекс вернул неожиданный формат. Сохранил ответ в {config.debug_dump_path}")

    route_names = set(config.routes)
    arrivals_by_route: dict[str, list[Arrival]] = {route: [] for route in config.routes}

    for transport in data.get("transports") or []:
        if not isinstance(transport, dict):
            continue

        route = str(transport.get("name") or "").strip()
        if route not in route_names:
            continue

        for thread in transport.get("threads") or []:
            if not isinstance(thread, dict) or thread.get("noBoarding") is True:
                continue
            arrivals_by_route[route].extend(parse_thread_events(route, thread))

    route_arrivals = []
    for route in config.routes:
        arrivals = sorted(
            arrivals_by_route.get(route, []),
            key=lambda item: item.timestamp if item.timestamp is not None else sys.maxsize,
        )
        route_arrivals.append(
            RouteArrivals(route=route, arrivals=tuple(arrivals[: config.arrivals_per_route]))
        )

    return ArrivalSnapshot(
        stop_name=str(data.get("name") or "").strip(),
        routes=tuple(route_arrivals),
        updated_at=datetime.now(),
    )


def parse_thread_events(route: str, thread: dict[str, Any]) -> list[Arrival]:
    brief_schedule = thread.get("BriefSchedule") or {}
    if not isinstance(brief_schedule, dict):
        return []

    arrivals = []
    for event in brief_schedule.get("Events") or []:
        arrival = parse_event(route, event)
        if arrival is not None:
            arrivals.append(arrival)

    if arrivals:
        return arrivals

    return []


def parse_event(route: str, event: Any) -> Arrival | None:
    if not isinstance(event, dict):
        return None

    departure = event.get("Estimated") or event.get("Scheduled")
    if not isinstance(departure, dict):
        return None

    text = str(departure.get("text") or "").strip()
    timestamp = None

    value = departure.get("value")
    if value is not None:
        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            timestamp = None

    if not text and timestamp is None:
        return None

    return Arrival(route=route, text=text, timestamp=timestamp)


def extract_stop_data(reply: dict[str, Any]) -> dict[str, Any] | None:
    data = reply.get("data")
    if isinstance(data, dict):
        return data

    stack = reply.get("stack")
    if isinstance(stack, list):
        for item in stack:
            if not isinstance(item, dict):
                continue
            stops = item.get("stops")
            if isinstance(stops, dict) and isinstance(stops.get("data"), dict):
                return stops["data"]

    app_config = reply.get("config")
    if isinstance(app_config, dict) and isinstance(app_config.get("masstransitStop"), dict):
        return app_config["masstransitStop"]

    return None


def save_debug_reply(config: YandexConfig, reply: Any) -> None:
    try:
        config.debug_dump_path.write_text(
            json.dumps(reply, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


class StateViewParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "script" and attrs_dict.get("class") == "state-view":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture:
            self._capture = False

    @property
    def payload(self) -> str:
        return "".join(self._chunks)


def parse_stop_page(config: YandexConfig, html: str) -> ArrivalSnapshot:
    parser = StateViewParser()
    parser.feed(html)

    if not parser.payload:
        raise ValueError("На странице остановки не найден JSON state-view")

    try:
        state = json.loads(parser.payload)
    except json.JSONDecodeError as error:
        raise ValueError("Не удалось прочитать JSON state-view со страницы остановки") from error

    return parse_yandex_reply(config, state)
