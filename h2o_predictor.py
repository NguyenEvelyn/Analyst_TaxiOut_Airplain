"""Nạp mô hình H2O đã huấn luyện trên Kaggle và tái tạo đặc trưng dự đoán."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class H2OTaxiOutPredictor:
    def __init__(self, deployment_dir: Path):
        import h2o

        self.h2o = h2o
        self.deployment_dir = Path(deployment_dir)
        with (self.deployment_dir / "metadata.json").open(encoding="utf-8") as file:
            self.metadata = json.load(file)

        self.origin_hour = pd.read_csv(self.deployment_dir / "origin_hour_hist.csv")
        self.route = pd.read_csv(self.deployment_dir / "route_hist.csv")
        self.carrier_origin = pd.read_csv(self.deployment_dir / "carrier_origin_hist.csv")
        self.origin_density = pd.read_csv(self.deployment_dir / "origin_density_hist.csv")

        h2o.init(nthreads=-1, max_mem_size="2G")
        self.model = h2o.load_model(str(self.deployment_dir / "h2o_taxiout_model"))

    @property
    def model_id(self) -> str:
        return self.metadata["model_id"]

    def _value(self, frame: pd.DataFrame, conditions: dict, column: str, default: float) -> float:
        mask = pd.Series(True, index=frame.index)
        for key, value in conditions.items():
            mask &= frame[key].astype(str) == str(value)
        matched = frame.loc[mask, column]
        return float(matched.iloc[0]) if not matched.empty else float(default)

    def predict(
        self,
        *,
        month: int,
        day: int,
        day_of_week: int,
        dep_hour: int,
        dep_minute: int,
        carrier: str,
        origin: str,
        dest: str,
        distance: float,
        departure_density: float,
    ) -> float:
        global_mean = float(self.metadata["global_train_mean"])
        half_hour_bin = ((dep_hour * 60 + dep_minute) // 30) * 30
        origin_avg_density = self._value(
            self.origin_density, {"Origin": origin}, "origin_avg_density", 1.0
        )

        row = {
            "Month": month,
            "DayofMonth": day,
            "DayOfWeek": day_of_week,
            "dep_hour": dep_hour,
            "half_hour_bin": half_hour_bin,
            "is_weekend": int(day_of_week in (6, 7)),
            "is_peak_hour": int(dep_hour in (7, 8, 9, 16, 17, 18, 19)),
            "UniqueCarrier": carrier,
            "Origin": origin,
            "Dest": dest,
            "Distance": distance,
            "departure_density_30m": departure_density,
            "relative_density": departure_density / max(origin_avg_density, 1.0),
            "origin_hour_hist_taxi": self._value(
                self.origin_hour,
                {"Origin": origin, "dep_hour": dep_hour},
                "origin_hour_hist_taxi",
                global_mean,
            ),
            "route_hist_taxi": self._value(
                self.route, {"Origin": origin, "Dest": dest}, "route_hist_taxi", global_mean
            ),
            "carrier_origin_hist_taxi": self._value(
                self.carrier_origin,
                {"UniqueCarrier": carrier, "Origin": origin},
                "carrier_origin_hist_taxi",
                global_mean,
            ),
            "origin_hour_hist_n": self._value(
                self.origin_hour,
                {"Origin": origin, "dep_hour": dep_hour},
                "origin_hour_hist_n",
                0,
            ),
            "route_hist_n": self._value(
                self.route, {"Origin": origin, "Dest": dest}, "route_hist_n", 0
            ),
        }

        frame = pd.DataFrame([row], columns=self.metadata["feature_columns"])
        for column in self.metadata["categorical_columns"]:
            frame[column] = frame[column].astype(str)

        h2o_frame = self.h2o.H2OFrame(frame)
        for column in self.metadata["categorical_columns"]:
            h2o_frame[column] = h2o_frame[column].asfactor()
        prediction = self.model.predict(h2o_frame).as_data_frame().iloc[0, 0]
        return float(prediction)


def deployment_is_ready(deployment_dir: Path) -> bool:
    required = {
        "h2o_taxiout_model",
        "metadata.json",
        "origin_hour_hist.csv",
        "route_hist.csv",
        "carrier_origin_hist.csv",
        "origin_density_hist.csv",
    }
    return all((Path(deployment_dir) / name).exists() for name in required)
