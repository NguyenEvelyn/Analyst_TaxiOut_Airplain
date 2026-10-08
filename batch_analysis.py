"""Validate uploaded flight CSVs and summarize batch H2O predictions."""

from io import BytesIO

import numpy as np
import pandas as pd

from live_feed import REQUIRED_COLUMNS, to_prediction_kwargs

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 2000


def parse_upload(contents: bytes) -> pd.DataFrame:
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ValueError("Tệp vượt 10 MB. Hãy chia tệp thành các phần nhỏ hoặc dùng Spark cho dữ liệu lớn.")
    try:
        frame = pd.read_csv(BytesIO(contents), dtype={
            "flight_id": str, "carrier": str, "origin": str, "dest": str,
        })
    except (UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError("Không đọc được CSV UTF-8. Kiểm tra dấu phân cách và mã hóa tệp.") from exc
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("CSV không có dòng dữ liệu.")
    if len(frame) > MAX_ROWS:
        raise ValueError(f"CSV có {len(frame):,} dòng; giao diện nhận tối đa {MAX_ROWS:,} dòng/lần.")
    frame = frame.copy()
    frame["scheduled_local"] = pd.to_datetime(frame["scheduled_local"], errors="coerce")
    for column in ("distance", "departure_density_30m"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("flight_id", "carrier", "origin", "dest"):
        frame[column] = frame[column].fillna("").astype(str).str.strip().str.upper()

    invalid = (
        frame["scheduled_local"].isna()
        | frame[["distance", "departure_density_30m"]].isna().any(axis=1)
        | frame["distance"].le(0)
        | frame["departure_density_30m"].lt(1)
        | frame[["flight_id", "carrier", "origin", "dest"]].eq("").any(axis=1)
        | frame["flight_id"].duplicated(keep=False)
    )
    if invalid.any():
        examples = ", ".join(str(n) for n in (frame.index[invalid][:8] + 2))
        raise ValueError(f"Có {int(invalid.sum())} dòng thiếu/sai dữ liệu hoặc trùng flight_id (dòng CSV: {examples}).")

    if "TaxiOut" in frame.columns:
        frame["TaxiOut"] = pd.to_numeric(frame["TaxiOut"], errors="coerce")
        bad_actual = frame["TaxiOut"].notna() & frame["TaxiOut"].lt(0)
        if bad_actual.any():
            raise ValueError("TaxiOut thực tế không được âm.")
    return frame


def predict_batch(predictor, frame: pd.DataFrame) -> pd.DataFrame:
    """Score all rows in one H2O request; do not train on uploaded data."""
    features = pd.concat(
        [predictor.build_feature_frame(**to_prediction_kwargs(row)) for _, row in frame.iterrows()],
        ignore_index=True,
    )
    h2o_frame = predictor.h2o.H2OFrame(features)
    for column in predictor.metadata["categorical_columns"]:
        h2o_frame[column] = h2o_frame[column].asfactor()
    values = predictor.model.predict(h2o_frame).as_data_frame().iloc[:, 0].to_numpy(dtype=float)
    result = frame.copy().reset_index(drop=True)
    result["predicted_taxi_out_minutes"] = values
    if "TaxiOut" in result.columns:
        result["absolute_error_minutes"] = (result["TaxiOut"] - values).abs()
    return result


def evaluation(result: pd.DataFrame) -> dict | None:
    if "TaxiOut" not in result.columns:
        return None
    valid = result["TaxiOut"].notna()
    if not valid.any():
        return None
    actual = result.loc[valid, "TaxiOut"].to_numpy(dtype=float)
    predicted = result.loc[valid, "predicted_taxi_out_minutes"].to_numpy(dtype=float)
    residual = actual - predicted
    return {
        "count": int(valid.sum()),
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "bias": float(np.mean(residual)),
    }
