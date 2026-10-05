"""End-to-end CSV snapshot -> feature conversion -> real H2O prediction smoke test."""

import tempfile
from pathlib import Path

from h2o_predictor import H2OTaxiOutPredictor
from live_feed import read_live_feed, to_prediction_kwargs


project_dir = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as directory:
    sample = Path(directory) / "live_flights.csv"
    sample.write_text(
        "flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m\n"
        "DL123,2026-10-05 08:30,DL,ATL,LGA,761,20\n",
        encoding="utf-8",
    )
    flights = read_live_feed(sample)
    predictor = H2OTaxiOutPredictor(project_dir / "taxiout_deployment_v3")
    minutes = predictor.predict(**to_prediction_kwargs(flights.iloc[0]))
    print(f"FEED_TEST_ROWS: {len(flights)}")
    print(f"MODEL_ID: {predictor.model_id}")
    print(f"PREDICTED_TAXI_OUT_MINUTES: {minutes:.2f}")
