from __future__ import annotations

import math
import time
from collections import Counter
from datetime import datetime

from curl_cffi import requests
from PySide6.QtGui import QImage

from transport_overlay.config import TrafficConfig
from transport_overlay.models import TrafficReading, TrafficSnapshot


# Yandex's website traffic overlay; this is an undocumented endpoint.
TILE_URL = "https://core-jams-rdr-cache.maps.yandex.net/1.1/tiles"
ZOOM = 17
TILE_SIZE = 256
SEARCH_RADIUS = 30  # About 27 metres at these latitudes.


def global_pixels(latitude: float, longitude: float, zoom: int = ZOOM) -> tuple[float, float]:
    """Yandex uses ellipsoidal WGS84 Mercator, not spherical Web Mercator."""
    eccentricity = 0.0818191908426
    phi = math.radians(latitude)
    sin_phi = math.sin(phi)
    correction = ((1 - eccentricity * sin_phi) / (1 + eccentricity * sin_phi)) ** (eccentricity / 2)
    size = TILE_SIZE * 2**zoom
    return (
        (longitude + 180) / 360 * size,
        (1 - math.log(math.tan(math.pi / 4 + phi / 2) * correction) / math.pi) / 2 * size,
    )


def traffic_color(red: int, green: int, blue: int, alpha: int) -> str | None:
    # Ignore transparent pixels, white outlines/arrows and grey roads.
    if alpha < 180 or max(red, green, blue) - min(red, green, blue) < 65:
        return None
    if green > red * 1.3 and green > blue * 1.3:
        return "green"
    if red > 180 and green > 210 and blue < 130:
        return "yellow"
    if red > 200 and 110 <= green <= 210 and blue < 130:
        return "orange"
    if red > 170 and green < 115 and blue < 130:
        return "red"
    if 90 < red <= 170 and green < 85 and blue < 85 and red > green * 1.5:
        return "darkred"
    return None


def sample_point(tiles: dict[tuple[int, int], QImage], x: float, y: float) -> str | None:
    candidates: list[tuple[float, str]] = []
    for py in range(math.floor(y - SEARCH_RADIUS), math.ceil(y + SEARCH_RADIUS) + 1):
        for px in range(math.floor(x - SEARCH_RADIUS), math.ceil(x + SEARCH_RADIUS) + 1):
            distance = math.hypot(px - x, py - y)
            if distance > SEARCH_RADIUS:
                continue
            tile = tiles[(px // TILE_SIZE, py // TILE_SIZE)]
            color = traffic_color(*tile.pixelColor(px % TILE_SIZE, py % TILE_SIZE).getRgb())
            if color is not None:
                candidates.append((distance, color))
    if not candidates:
        return None
    nearest = min(distance for distance, _ in candidates)
    # A small band around the nearest line avoids choosing a single antialiased pixel.
    counts = Counter(color for distance, color in candidates if distance <= nearest + 2)
    return counts.most_common(1)[0][0]


def fetch_traffic_snapshot(config: TrafficConfig) -> TrafficSnapshot:
    tiles: dict[tuple[int, int], QImage] = {}
    failures: dict[tuple[int, int], str] = {}
    readings = []
    # All tiles in one update use the same cache bucket. Never reuse a previous
    # reading after a failed request; unknown is different from free traffic.
    bucket = int(time.time() // config.poll_seconds)
    with requests.Session(impersonate="chrome") as session:
        for point in config.points:
            x, y = global_pixels(point.latitude, point.longitude)
            try:
                for tx in range(math.floor((x - SEARCH_RADIUS) / TILE_SIZE), math.floor((x + SEARCH_RADIUS) / TILE_SIZE) + 1):
                    for ty in range(math.floor((y - SEARCH_RADIUS) / TILE_SIZE), math.floor((y + SEARCH_RADIUS) / TILE_SIZE) + 1):
                        key = (tx, ty)
                        if key in failures:
                            raise RuntimeError(failures[key])
                        if key in tiles:
                            continue
                        try:
                            response = session.get(
                                TILE_URL,
                                params={"l": "trf", "x": tx, "y": ty, "z": ZOOM, "scale": 1, "lang": "ru_RU", "_": bucket},
                                timeout=10,
                            )
                            response.raise_for_status()
                            tile = QImage.fromData(response.content)
                            if tile.isNull() or tile.width() != TILE_SIZE or tile.height() != TILE_SIZE:
                                raise RuntimeError("Яндекс не вернул изображение пробок")
                            tiles[key] = tile
                        except Exception as error:
                            failures[key] = str(error)
                            raise
                level = sample_point(tiles, x, y)
                readings.append(TrafficReading(point.name, level, None if level else "Рядом с точкой нет цветной линии пробок"))
            except Exception as error:
                readings.append(TrafficReading(point.name, error=str(error)))
    return TrafficSnapshot(tuple(readings), datetime.now())
