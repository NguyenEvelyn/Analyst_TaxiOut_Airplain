import unittest

import pandas as pd

from batch_analysis import evaluation, parse_upload


HEADER = "flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m,TaxiOut\n"


class BatchAnalysisTests(unittest.TestCase):
    def test_parse_valid_csv(self):
        frame = parse_upload((HEADER + "DL123,2008-11-15 08:30,DL,ATL,LGA,761,30,22\n").encode())
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.loc[0, "origin"], "ATL")

    def test_missing_column_is_explained(self):
        with self.assertRaisesRegex(ValueError, "Thiếu cột bắt buộc"):
            parse_upload(b"flight_id,scheduled_local\nDL123,2008-11-15 08:30\n")

    def test_duplicate_flight_id_is_rejected(self):
        row = "DL123,2008-11-15 08:30,DL,ATL,LGA,761,30,22\n"
        with self.assertRaisesRegex(ValueError, "trùng flight_id"):
            parse_upload((HEADER + row + row).encode())

    def test_evaluation_only_uses_labeled_rows(self):
        frame = pd.DataFrame({"TaxiOut": [20.0, None], "predicted_taxi_out_minutes": [18.0, 100.0]})
        result = evaluation(frame)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["mae"], 2.0)


if __name__ == "__main__":
    unittest.main()
