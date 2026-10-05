"""Small, explicitly labeled dashboard views derived from exported training statistics."""

import json
from pathlib import Path

import pandas as pd


def training_hourly_profile(deployment_dir: Path, airport_codes: list[str]) -> pd.DataFrame:
    """Recover Jan-Sep 2008 means from the smoothed Origin-hour lookup table.

    The training notebook used (sum(TaxiOut) + 100 * global_mean) / (n + 100).
    This is not the all-year congestion-window export from Kaggle.
    """
    metadata = json.loads((deployment_dir / "metadata.json").read_text(encoding="utf-8"))
    history = pd.read_csv(deployment_dir / "origin_hour_hist.csv")
    history = history.loc[history["Origin"].isin(airport_codes)].copy()
    history = history.loc[history["origin_hour_hist_n"] > 0]
    count = history["origin_hour_hist_n"]
    smoothed = history["origin_hour_hist_taxi"]
    global_mean = float(metadata["global_train_mean"])
    history["avg_taxi_out"] = ((count + 100) * smoothed - 100 * global_mean) / count
    history = history.rename(columns={"origin_hour_hist_n": "flights"})
    return history[["Origin", "dep_hour", "flights", "avg_taxi_out"]].sort_values(
        ["Origin", "dep_hour"]
    )
