"""Quick smoke test for the exported TaxiOut model in Ubuntu/WSL."""

from pathlib import Path

from h2o_predictor import H2OTaxiOutPredictor, deployment_is_ready


model_dir = Path(__file__).resolve().parent / "taxiout_deployment_v3"
if not deployment_is_ready(model_dir):
    raise SystemExit(f"Missing deployment files in: {model_dir}")

predictor = H2OTaxiOutPredictor(model_dir)
minutes = predictor.predict(
    month=1,
    day=15,
    day_of_week=2,
    dep_hour=8,
    dep_minute=30,
    carrier="DL",
    origin="ATL",
    dest="LGA",
    distance=761,
    departure_density=20,
)
print(f"MODEL_ID: {predictor.model_id}")
print(f"PREDICTED_TAXI_OUT_MINUTES: {minutes:.2f}")
