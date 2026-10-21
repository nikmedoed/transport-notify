import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from PySide6.QtGui import QColor, QImage

from transport_overlay.config import load_config
from transport_overlay.models import TrafficReading, TrafficSnapshot
from transport_overlay.poller import BusPoller
from transport_overlay.traffic import global_pixels, sample_point, traffic_color


class TrafficTests(unittest.TestCase):
    def test_yandex_ellipsoidal_projection(self):
        x, y = global_pixels(40.202858, 44.543535, 16)
        self.assertAlmostEqual(x, 10464487.189162666, places=5)
        self.assertAlmostEqual(y, 6350693.85852286, places=5)

    def test_palette_and_non_traffic_pixels(self):
        for rgba, expected in [
            ((94, 205, 76, 255), "green"),
            ((255, 230, 0, 255), "yellow"),
            ((255, 187, 51, 255), "orange"),
            ((230, 90, 70, 255), "red"),
            ((143, 53, 30, 255), "darkred"),
            ((255, 255, 255, 255), None),
            ((140, 140, 140, 255), None),
            ((230, 90, 70, 20), None),
        ]:
            with self.subTest(rgba=rgba):
                self.assertEqual(traffic_color(*rgba), expected)

    def test_nearest_road_across_tile_boundary(self):
        tiles = {}
        for tx in (0, 1):
            image = QImage(256, 256, QImage.Format.Format_ARGB32)
            image.fill(QColor(0, 0, 0, 0))
            tiles[(tx, 0)] = image
        for y in range(70, 130):
            tiles[(1, 0)].setPixelColor(1, y, QColor(230, 90, 70))
            tiles[(0, 0)].setPixelColor(240, y, QColor(94, 205, 76))
        self.assertEqual(sample_point(tiles, 255, 100), "red")

    def test_empty_tile_is_unknown(self):
        image = QImage(256, 256, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        self.assertIsNone(sample_point({(0, 0): image}, 100, 100))

    def test_average_requires_all_points(self):
        readings = (TrafficReading("a", "green"), TrafficReading("b", "orange"), TrafficReading("c", "red"))
        self.assertAlmostEqual(TrafficSnapshot(readings, datetime.now()).average, 17 / 3)
        self.assertIsNone(TrafficSnapshot(readings[:2] + (TrafficReading("c"),), datetime.now()).average)

    def test_traffic_survives_bus_failure_and_obeys_interval(self):
        poller = BusPoller(load_config())
        poller._tracking_enabled_event.set()
        traffic = TrafficSnapshot(tuple(TrafficReading(p.name, "green") for p in poller.config.traffic.points), datetime.now())
        received, errors = [], []
        poller.traffic_ready.connect(received.append)
        poller.error_ready.connect(errors.append)
        with patch.object(poller, "fetch_snapshot", AsyncMock(side_effect=RuntimeError("bus unavailable"))), patch(
            "transport_overlay.poller.fetch_traffic_snapshot", return_value=traffic
        ) as fetch:
            asyncio.run(poller._poll_once())
            asyncio.run(poller._poll_once())
        self.assertEqual(received, [traffic])
        self.assertEqual(errors, ["bus unavailable", "bus unavailable"])
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
