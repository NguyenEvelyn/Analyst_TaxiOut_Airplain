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


# BƯỚC 13 - Phân tích sai số theo sân bay, giờ và mức TaxiOut thực tế
pred_v3 = leader_v3.predict(test_v3).as_data_frame()["predict"].to_numpy()
error_analysis = test_v3_pd[["Origin", "dep_hour", "TaxiOut"]].copy()
error_analysis["prediction"] = pred_v3
error_analysis["residual"] = error_analysis["TaxiOut"] - error_analysis["prediction"]
error_analysis["absolute_error"] = error_analysis["residual"].abs()
error_analysis["actual_band"] = pd.cut(
    error_analysis["TaxiOut"], bins=[0, 10, 20, 30, 60, float("inf")],
    labels=["<=10", "11-20", "21-30", "31-60", ">60"]
)

error_by_airport = (error_analysis.groupby("Origin")
    .agg(rows=("absolute_error", "size"), MAE=("absolute_error", "mean"),
         bias=("residual", "mean"))
    .query("rows >= 100").sort_values("MAE", ascending=False).reset_index())
error_by_hour = (error_analysis.groupby("dep_hour")
    .agg(rows=("absolute_error", "size"), MAE=("absolute_error", "mean"),
         bias=("residual", "mean")).reset_index())
error_by_band = (error_analysis.groupby("actual_band", observed=True)
    .agg(rows=("absolute_error", "size"), MAE=("absolute_error", "mean"),
         bias=("residual", "mean")).reset_index())

error_by_airport.to_csv("/kaggle/working/error_by_airport_v3.csv", index=False)
error_by_hour.to_csv("/kaggle/working/error_by_hour_v3.csv", index=False)
error_by_band.to_csv("/kaggle/working/error_by_taxi_band_v3.csv", index=False)

display(error_by_band)
display(error_by_airport.head(20))
px.line(error_by_hour, x="dep_hour", y="MAE", markers=True,
        title="MAE theo giờ khởi hành").show()
