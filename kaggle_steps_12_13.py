# BƯỚC 12 - Trực quan hóa so sánh mô hình
import plotly.express as px

comparison_long = comparison.melt(
    id_vars="model", value_vars=["MAE", "RMSE"],
    var_name="metric", value_name="minutes"
)
fig_metrics = px.bar(
    comparison_long, x="model", y="minutes", color="metric", barmode="group",
    title="So sánh sai số mô hình trên tập kiểm tra tháng 11-12/2008",
    labels={"model": "Mô hình", "minutes": "Sai số (phút)", "metric": "Chỉ số"}
)
fig_metrics.show()


# BƯỚC 13 - Xuất bằng chứng cấp chuyến và phân tích sai số đa chiều
import json
from pathlib import Path

from evaluation import (
    add_error_columns,
    bootstrap_mae_by_group,
    build_evaluation_exports,
)

OUTPUT_DIR = Path("/kaggle/working")
pred_v3 = leader_v3.predict(test_v3).as_data_frame()["predict"].to_numpy()
prediction_columns = [
    "Month", "DayofMonth", "DayOfWeek", "dep_hour", "half_hour_bin",
    "UniqueCarrier", "Origin", "Dest", "Distance", "departure_density_30m",
    "relative_density", "TaxiOut",
]
error_analysis = test_v3_pd[prediction_columns].copy()
error_analysis["prediction"] = pred_v3
error_analysis["flight_date"] = pd.to_datetime(
    {"year": 2008, "month": error_analysis["Month"], "day": error_analysis["DayofMonth"]},
    errors="coerce",
)
error_analysis = add_error_columns(error_analysis)

# CSV is portable; Parquet keeps types and is preferred for later analysis.
error_analysis.to_csv(OUTPUT_DIR / "test_predictions_v3.csv", index=False)
try:
    error_analysis.to_parquet(OUTPUT_DIR / "test_predictions_v3.parquet", index=False)
except (ImportError, ModuleNotFoundError) as exc:
    print("Không xuất được Parquet; file CSV vẫn đầy đủ:", exc)

exports = {export.name: export.frame for export in build_evaluation_exports(error_analysis)}
for name, frame in exports.items():
    frame.to_csv(OUTPUT_DIR / name, index=False)

error_by_airport = exports["error_by_airport_v3.csv"]
error_by_hour = exports["error_by_hour_v3.csv"]
error_by_band = exports["error_by_taxi_band_v3.csv"]

confidence = bootstrap_mae_by_group(
    error_analysis.dropna(subset=["flight_date"]),
    "flight_date",
    iterations=2000,
    seed=52,
)
confidence["within_5_minutes_pct"] = float((error_analysis["absolute_error"] <= 5).mean() * 100)
confidence["within_10_minutes_pct"] = float((error_analysis["absolute_error"] <= 10).mean() * 100)
confidence["within_15_minutes_pct"] = float((error_analysis["absolute_error"] <= 15).mean() * 100)
(OUTPUT_DIR / "model_confidence_v3.json").write_text(
    json.dumps(confidence, indent=2), encoding="utf-8"
)

display(error_by_band)
display(error_by_airport.head(20))
px.line(error_by_hour, x="dep_hour", y="MAE", markers=True,
        title="MAE theo giờ khởi hành").show()
