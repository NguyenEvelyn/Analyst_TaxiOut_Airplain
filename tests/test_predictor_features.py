import unittest

import pandas as pd

from h2o_predictor import H2OTaxiOutPredictor


class PredictorFeatureTests(unittest.TestCase):
    def setUp(self):
        predictor = H2OTaxiOutPredictor.__new__(H2OTaxiOutPredictor)
        predictor.metadata = {
            "global_train_mean": 16.5,
            "feature_columns": [
                "Month", "DayofMonth", "DayOfWeek", "dep_hour", "half_hour_bin",
                "is_weekend", "is_peak_hour", "UniqueCarrier", "Origin", "Dest",
                "Distance", "departure_density_30m", "relative_density",
                "origin_hour_hist_taxi", "route_hist_taxi", "carrier_origin_hist_taxi",
                "origin_hour_hist_n", "route_hist_n",
            ],
            "categorical_columns": [
                "DayofMonth", "DayOfWeek", "dep_hour", "half_hour_bin", "is_weekend",
                "is_peak_hour", "UniqueCarrier", "Origin", "Dest",
            ],
            "category_levels": {
                "UniqueCarrier": ["DL"], "Origin": ["ATL"], "Dest": ["LGA"]
            },
            "relative_density_warning_threshold": 4.0,
        }
        predictor.origin_hour = pd.DataFrame([
            {"Origin": "ATL", "dep_hour": 8, "origin_hour_hist_taxi": 20.0,
             "origin_hour_hist_n": 1000}
        ])
        predictor.route = pd.DataFrame([
            {"Origin": "ATL", "Dest": "LGA", "route_hist_taxi": 21.0, "route_hist_n": 500}
        ])
        predictor.carrier_origin = pd.DataFrame([
            {"UniqueCarrier": "DL", "Origin": "ATL", "carrier_origin_hist_taxi": 19.0}
        ])
        predictor.origin_density = pd.DataFrame([
            {"Origin": "ATL", "origin_avg_density": 10.0}
        ])
        self.predictor = predictor

    def test_feature_order_half_hour_and_categories(self):
        frame = self.predictor.build_feature_frame(
            month=11, day=3, day_of_week=1, dep_hour=8, dep_minute=44,
            carrier="dl", origin="atl", dest="lga", distance=761,
            departure_density=20,
        )
        self.assertEqual(frame.columns.tolist(), self.predictor.metadata["feature_columns"])
        self.assertEqual(frame.loc[0, "half_hour_bin"], "510")
        self.assertEqual(frame.loc[0, "Origin"], "ATL")
        self.assertEqual(frame.loc[0, "relative_density"], 2.0)

    def test_unknown_route_uses_global_fallback_and_warns(self):
        frame = self.predictor.build_feature_frame(
            month=11, day=3, day_of_week=1, dep_hour=8, dep_minute=30,
            carrier="XX", origin="ATL", dest="ZZZ", distance=500,
            departure_density=60,
        )
        self.assertEqual(frame.loc[0, "route_hist_taxi"], 16.5)
        self.assertEqual(frame.loc[0, "route_hist_n"], 0.0)
        warnings = self.predictor.assess_input(
            carrier="XX", origin="ATL", dest="ZZZ", departure_density=60
        )
        self.assertTrue(any("hãng bay" in item for item in warnings))
        self.assertTrue(any("tuyến bay" in item for item in warnings))
        self.assertTrue(any("mật độ tương đối" in item for item in warnings))

    def test_invalid_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "departure time"):
            self.predictor.build_feature_frame(
                month=11, day=3, day_of_week=1, dep_hour=24, dep_minute=0,
                carrier="DL", origin="ATL", dest="LGA", distance=761,
                departure_density=20,
            )

    def test_invalid_calendar_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid calendar date"):
            self.predictor.build_feature_frame(
                month=2, day=31, day_of_week=1, dep_hour=8, dep_minute=0,
                carrier="DL", origin="ATL", dest="LGA", distance=761,
                departure_density=20,
            )


if __name__ == "__main__":
    unittest.main()
