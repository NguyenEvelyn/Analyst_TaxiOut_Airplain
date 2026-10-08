"""Deterministic evaluation helpers shared by Kaggle exports and local tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_PREDICTION_COLUMNS = {
    "TaxiOut",
    "prediction",
    "Origin",
    "Dest",
    "UniqueCarrier",
    "dep_hour",
    "departure_density_30m",
}


def add_error_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with residual, absolute error and stable analysis bands."""
    missing = REQUIRED_PREDICTION_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Prediction frame missing columns: {', '.join(sorted(missing))}")
    result = frame.copy()
    result["residual"] = result["TaxiOut"] - result["prediction"]
    result["absolute_error"] = result["residual"].abs()
    result["actual_band"] = pd.cut(
        result["TaxiOut"],
        bins=[0, 10, 20, 30, 60, float("inf")],
        labels=["<=10", "11-20", "21-30", "31-60", ">60"],
    )
    result["density_band"] = pd.cut(
        result["departure_density_30m"],
        bins=[0, 2, 5, 10, 20, float("inf")],
        labels=["1-2", "3-5", "6-10", "11-20", ">20"],
        include_lowest=True,
    )
    result["route"] = result["Origin"].astype(str) + "-" + result["Dest"].astype(str)
    return result


def summarize_error(frame: pd.DataFrame, group_columns: list[str], min_rows: int = 1) -> pd.DataFrame:
    """Aggregate count, MAE, RMSE and signed bias for one or more dimensions."""
    required = {"residual", "absolute_error", *group_columns}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Error frame missing columns: {', '.join(sorted(missing))}")
    grouped = (
        frame.groupby(group_columns, observed=True, dropna=False)
        .agg(
            rows=("absolute_error", "size"),
            MAE=("absolute_error", "mean"),
            MSE=("residual", lambda values: float(np.mean(np.square(values)))),
            bias=("residual", "mean"),
        )
        .reset_index()
    )
    grouped["RMSE"] = np.sqrt(grouped.pop("MSE"))
    return grouped.loc[grouped["rows"] >= min_rows].reset_index(drop=True)


def bootstrap_mae_by_group(
    frame: pd.DataFrame,
    group_column: str,
    *,
    iterations: int = 1000,
    seed: int = 52,
) -> dict[str, float]:
    """Bootstrap MAE by resampling whole groups such as flight dates."""
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    required = {group_column, "absolute_error"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Bootstrap frame missing columns: {', '.join(sorted(missing))}")
    grouped = frame.groupby(group_column, dropna=False)["absolute_error"].agg(["sum", "count"])
    if len(grouped) < 2:
        raise ValueError("bootstrap requires at least two groups")
    rng = np.random.default_rng(seed)
    sums = grouped["sum"].to_numpy(dtype=float)
    counts = grouped["count"].to_numpy(dtype=float)
    estimates = np.empty(iterations, dtype=float)
    for index in range(iterations):
        sample = rng.integers(0, len(grouped), size=len(grouped))
        estimates[index] = sums[sample].sum() / counts[sample].sum()
    return {
        "mae": float(frame["absolute_error"].mean()),
        "ci95_lower": float(np.quantile(estimates, 0.025)),
        "ci95_upper": float(np.quantile(estimates, 0.975)),
        "bootstrap_groups": int(len(grouped)),
        "bootstrap_iterations": int(iterations),
        "bootstrap_seed": int(seed),
    }


@dataclass(frozen=True)
class EvaluationExport:
    name: str
    frame: pd.DataFrame


def build_evaluation_exports(predictions: pd.DataFrame) -> list[EvaluationExport]:
    """Build all report tables from one prediction-level source of truth."""
    errors = add_error_columns(predictions)
    return [
        EvaluationExport("error_by_airport_v3.csv", summarize_error(errors, ["Origin"], 100).sort_values("MAE", ascending=False)),
        EvaluationExport("error_by_hour_v3.csv", summarize_error(errors, ["dep_hour"]).sort_values("dep_hour")),
        EvaluationExport("error_by_taxi_band_v3.csv", summarize_error(errors, ["actual_band"])),
        EvaluationExport("error_by_carrier_v3.csv", summarize_error(errors, ["UniqueCarrier"], 100).sort_values("MAE", ascending=False)),
        EvaluationExport("error_by_density_band_v3.csv", summarize_error(errors, ["density_band"])),
        EvaluationExport("error_by_route_v3.csv", summarize_error(errors, ["route"], 100).sort_values("MAE", ascending=False)),
    ]


def write_evaluation_exports(predictions: pd.DataFrame, output_dir: Path) -> None:
    """Write prediction-level evidence and all aggregate error tables."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    errors = add_error_columns(predictions)
    errors.to_csv(output_dir / "test_predictions_v3.csv", index=False)
    try:
        errors.to_parquet(output_dir / "test_predictions_v3.parquet", index=False)
    except (ImportError, ModuleNotFoundError):
        # CSV remains the portable required artifact when pyarrow is unavailable.
        pass
    for export in build_evaluation_exports(predictions):
        export.frame.to_csv(output_dir / export.name, index=False)
