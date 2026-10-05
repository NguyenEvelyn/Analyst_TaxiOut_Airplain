import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard_data import training_hourly_profile
from live_feed import aviationstack_to_feed, read_live_feed, to_prediction_kwargs


ROOT = Path(__file__).resolve().parents[1]


class DashboardDataTests(unittest.TestCase):
    def test_historical_hourly_profile(self):
        result = training_hourly_profile(ROOT / "taxiout_deployment_v3", ["ATL", "LGA"])
        self.assertEqual(set(result["Origin"]), {"ATL", "LGA"})
        self.assertTrue(result["flights"].gt(0).all())
        self.assertTrue(result["avg_taxi_out"].between(1, 180).all())

    def test_live_feed_validation_and_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "live_flights.csv"
            path.write_text(
                "flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m\n"
                "DL123,2026-10-05 08:30,DL,ATL,LGA,761,20\n",
                encoding="utf-8",
            )
            result = read_live_feed(path)
            self.assertEqual(len(result), 1)
            kwargs = to_prediction_kwargs(result.iloc[0])
            self.assertEqual((kwargs["month"], kwargs["day"], kwargs["day_of_week"]), (10, 5, 1))
            self.assertEqual(kwargs["departure_density"], 20.0)

    def test_live_feed_rejects_missing_density(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "live_flights.csv"
            pd.DataFrame([{"flight_id": "DL123", "scheduled_local": "2026-10-05 08:30"}]).to_csv(
                path, index=False
            )
            with self.assertRaisesRegex(ValueError, "departure_density_30m"):
                read_live_feed(path)

    def test_aviationstack_payload_is_normalized(self):
        locations = pd.DataFrame(
            [
                {"Origin": "ATL", "latitude": 33.6407, "longitude": -84.4277},
                {"Origin": "LGA", "latitude": 40.7769, "longitude": -73.8740},
            ]
        )
        payload = {
            "data": [
                {
                    "flight_status": "scheduled",
                    "departure": {"iata": "ATL", "scheduled": "2026-10-02T08:10:00-04:00"},
                    "arrival": {"iata": "LGA"},
                    "airline": {"iata": "DL"},
                    "flight": {"iata": "DL123"},
                },
                {
                    "flight_status": "scheduled",
                    "departure": {"iata": "ATL", "scheduled": "2026-10-02T08:20:00-04:00"},
                    "arrival": {"iata": "LGA"},
                    "airline": {"iata": "DL"},
                    "flight": {"iata": "DL124"},
                },
            ]
        }
        result = aviationstack_to_feed(payload, locations)
        self.assertEqual(result["flight_id"].tolist(), ["DL123", "DL124"])
        self.assertEqual(result["departure_density_30m"].tolist(), [2, 2])
        self.assertTrue(result["distance"].between(750, 780).all())


if __name__ == "__main__":
    unittest.main()
