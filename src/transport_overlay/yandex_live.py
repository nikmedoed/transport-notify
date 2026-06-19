from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

from curl_cffi import requests

from transport_overlay.config import YandexConfig
from transport_overlay.models import ArrivalSnapshot
from transport_overlay.yandex_source import StateViewParser, parse_yandex_reply


API_BASE_URL = "https://yandex.com/maps/api"


def fetch_yandex_snapshot(config: YandexConfig) -> ArrivalSnapshot:
    stop_id = first_numeric_stop_id(config.stop_ids)
    page_url = config.stop_page_url_template.format(stop_id=stop_id)

    with requests.Session(impersonate="chrome") as session:
        page_response = session.get(
            cache_busted_url(page_url),
            headers=page_headers(config),
            timeout=20,
        )
        page_response.raise_for_status()
        if "captcha" in str(page_response.url):
            raise RuntimeError("Яндекс показал капчу. Увеличь poll_seconds или подожди.")

        state = parse_state_view(page_response.text)
        live_reply = fetch_live_stop_info(
            session=session,
            config=config,
            state=state,
            stop_id=stop_id,
            retpath=str(page_response.url),
        )
        return parse_yandex_reply(config, live_reply)


def fetch_live_stop_info(
    session: requests.Session,
    config: YandexConfig,
    state: dict[str, Any],
    stop_id: str,
    retpath: str,
) -> dict[str, Any]:
    app_config = state.get("config") or {}
    csrf_token = str(app_config["csrfToken"])
    session_id = str(app_config["counters"]["analytics"]["sessionId"])

    for _ in range(2):
        params = live_stop_params(app_config, stop_id, csrf_token, session_id, config.arrivals_per_route)
        response = session.get(
            f"{API_BASE_URL}/masstransit/getStopInfo",
            params=signed_pairs(params),
            headers=api_headers(config, retpath),
            timeout=20,
        )
        response.raise_for_status()
        reply = response.json()

        if set(reply) == {"csrfToken"}:
            csrf_token = str(reply["csrfToken"])
            continue

        return reply

    raise RuntimeError("Яндекс не отдал live-прогноз, только обновил csrfToken.")


def live_stop_params(
    app_config: dict[str, Any],
    stop_id: str,
    csrf_token: str,
    session_id: str,
    arrivals_per_route: int,
) -> dict[str, Any]:
    results = max(6, arrivals_per_route * 2)
    return {
        "ajax": "1",
        "csrfToken": csrf_token,
        "id": stop_id,
        "lang": app_config.get("lang", "ru"),
        "locale": app_config.get("realLocale", "ru_AM"),
        "mode": "prognosis",
        "results": str(results),
        "rll": "",
        "sessionId": session_id,
        "timeDependent": {
            "time": datetime.now().replace(second=0, microsecond=0).isoformat(timespec="seconds"),
            "type": "departure",
        },
    }


def signed_pairs(params: dict[str, Any]) -> list[tuple[str, str]]:
    signed = dict(params)
    signed["s"] = signature(params)
    return flatten_params(signed)


def signature(params: dict[str, Any]) -> str:
    text = query_string(flatten_params(params))
    value = 5381
    for char in text:
        value = (33 * value) ^ ord(char)
    return str(value & 0xFFFFFFFF)


def flatten_params(params: dict[str, Any]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []

    def add(prefix: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for key in sorted(value, key=str.lower):
                add(f"{prefix}[{key}]", value[key])
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                add(f"{prefix}[{index}]", item)
            return
        result.append((prefix, str(value).lower() if isinstance(value, bool) else str(value)))

    for key in sorted(params, key=str.lower):
        add(key, params[key])

    return result


def query_string(pairs: list[tuple[str, str]]) -> str:
    return "&".join(f"{quote(key, safe='-._~')}={quote(value, safe='-._~')}" for key, value in pairs)


def parse_state_view(html: str) -> dict[str, Any]:
    parser = StateViewParser()
    parser.feed(html)

    if not parser.payload:
        raise ValueError("На странице остановки не найден JSON state-view")

    return json.loads(parser.payload)


def cache_busted_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_={time.time_ns()}"


def page_headers(config: YandexConfig) -> dict[str, str]:
    return {
        "User-Agent": config.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def api_headers(config: YandexConfig, retpath: str) -> dict[str, str]:
    return {
        "User-Agent": config.user_agent,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": retpath,
        "X-Retpath-Y": retpath,
        "viewport-width": "1484",
        "sec-ch-viewport-height": "985",
        "sec-ch-viewport-width": "1484",
        "device-memory": "32",
        "dpr": "1",
        "rtt": "100",
        "downlink": "1.55",
        "ect": "4g",
    }


def first_numeric_stop_id(stop_ids: tuple[str, ...]) -> str:
    if not stop_ids:
        raise RuntimeError("В config.toml не задан yandex.stop_ids")

    for stop_id in stop_ids:
        cleaned = stop_id.removeprefix("stop__")
        if cleaned.isdigit():
            return cleaned

    return stop_ids[0].removeprefix("stop__")
