import unittest

import pandas as pd

from evaluation import (
    add_error_columns,
    bootstrap_mae_by_group,
    build_evaluation_exports,
    summarize_error,
)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.predictions = pd.DataFrame(
            [
                {"flight_date": "2008-11-01", "TaxiOut": 10, "prediction": 12,
                 "Origin": "ATL", "Dest": "LGA", "UniqueCarrier": "DL",
                 "dep_hour": 8, "departure_density_30m": 20},
                {"flight_date": "2008-11-01", "TaxiOut": 20, "prediction": 15,
                 "Origin": "ATL", "Dest": "JFK", "UniqueCarrier": "DL",
                 "dep_hour": 8, "departure_density_30m": 20},
                {"flight_date": "2008-11-02", "TaxiOut": 70, "prediction": 25,
                 "Origin": "JFK", "Dest": "LAX", "UniqueCarrier": "AA",
                 "dep_hour": 19, "departure_density_30m": 30},
            ]
        )

    def test_error_columns_use_actual_minus_prediction(self):
        result = add_error_columns(self.predictions)
        self.assertEqual(result["residual"].tolist(), [-2, 5, 45])
        self.assertEqual(result["absolute_error"].tolist(), [2, 5, 45])
        self.assertEqual(result["actual_band"].astype(str).tolist(), ["<=10", "11-20", ">60"])

    def test_summary_computes_mae_rmse_and_bias(self):
        result = summarize_error(add_error_columns(self.predictions), ["Origin"])
        atl = result.loc[result["Origin"] == "ATL"].iloc[0]
        self.assertAlmostEqual(atl["MAE"], 3.5)
        self.assertAlmostEqual(atl["bias"], 1.5)
        self.assertAlmostEqual(atl["RMSE"], (29 / 2) ** 0.5)

    def test_exports_have_one_prediction_source_of_truth(self):
        names = {item.name for item in build_evaluation_exports(self.predictions)}
        self.assertIn("error_by_hour_v3.csv", names)
        self.assertIn("error_by_route_v3.csv", names)
        self.assertIn("error_by_density_band_v3.csv", names)

    def test_group_bootstrap_is_reproducible(self):
        errors = add_error_columns(self.predictions)
        first = bootstrap_mae_by_group(errors, "flight_date", iterations=200, seed=52)
        second = bootstrap_mae_by_group(errors, "flight_date", iterations=200, seed=52)
        self.assertEqual(first, second)
        self.assertLessEqual(first["ci95_lower"], first["mae"])
        self.assertGreaterEqual(first["ci95_upper"], first["mae"])


if __name__ == "__main__":
    unittest.main()
