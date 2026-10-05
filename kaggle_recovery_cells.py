"""Backup các cell Kaggle quan trọng khi draft bị ConcurrencyViolation.

Các cell này đã được chạy thành công trong notebook BigData ngày 2026-09-29.
Kết quả v3: MAE=5.841377, RMSE=10.075190, R2=0.203307.
"""

# %% BƯỚC 4 - Khởi tạo Apache Spark cho ETL phân tán
try:
    import pyspark
    from pyspark.sql import SparkSession, functions as F

    spark = (
        SparkSession.builder
        .appName("AirportTaxiTime")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.shuffle.partitions", "90")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    print("PySpark version:", pyspark.__version__)
    print("Spark session:", spark.version)
    print("PYSPARK_AVAILABLE=True")
except ImportError as exc:
    print("PYSPARK_AVAILABLE=False")
    print("Cần cài pyspark trước khi chạy bước Spark ETL:", exc)


# %% BƯỚC 11 - Cải thiện mô hình bằng historical encoding
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

features_base = spark.read.parquet(feature_2008_path)
train_history = features_base.filter(F.col("Month") <= 9)
global_train_mean = float(train_history.agg(F.avg("TaxiOut")).first()[0])

# Chỉ tính thống kê từ tháng 1-9 để không rò rỉ dữ liệu sang validation/test.
origin_hour_hist = (
    train_history.groupBy("Origin", "dep_hour")
    .agg(F.sum("TaxiOut").alias("oh_sum"), F.count("*").alias("origin_hour_hist_n"))
    .withColumn(
        "origin_hour_hist_taxi",
        (F.col("oh_sum") + F.lit(100.0 * global_train_mean))
        / (F.col("origin_hour_hist_n") + F.lit(100.0)),
    )
    .drop("oh_sum")
)
route_hist = (
    train_history.groupBy("Origin", "Dest")
    .agg(F.sum("TaxiOut").alias("route_sum"), F.count("*").alias("route_hist_n"))
    .withColumn(
        "route_hist_taxi",
        (F.col("route_sum") + F.lit(50.0 * global_train_mean))
        / (F.col("route_hist_n") + F.lit(50.0)),
    )
    .drop("route_sum")
)
carrier_origin_hist = train_history.groupBy("UniqueCarrier", "Origin").agg(
    F.avg("TaxiOut").alias("carrier_origin_hist_taxi")
)
origin_density_hist = train_history.groupBy("Origin").agg(
    F.avg("departure_density_30m").alias("origin_avg_density")
)

features_enhanced = (
    features_base
    .join(F.broadcast(origin_hour_hist), ["Origin", "dep_hour"], "left")
    .join(F.broadcast(route_hist), ["Origin", "Dest"], "left")
    .join(F.broadcast(carrier_origin_hist), ["UniqueCarrier", "Origin"], "left")
    .join(F.broadcast(origin_density_hist), ["Origin"], "left")
    .fillna({
        "origin_hour_hist_taxi": global_train_mean,
        "route_hist_taxi": global_train_mean,
        "carrier_origin_hist_taxi": global_train_mean,
        "origin_avg_density": 1.0,
        "origin_hour_hist_n": 0,
        "route_hist_n": 0,
    })
    .withColumn(
        "relative_density",
        F.col("departure_density_30m") / F.greatest(F.col("origin_avg_density"), F.lit(1.0)),
    )
    .withColumn(
        "is_peak_hour",
        F.when(F.col("dep_hour").isin([7, 8, 9, 16, 17, 18, 19]), 1).otherwise(0),
    )
)

enhanced_cols = [
    "Month", "DayofMonth", "DayOfWeek", "dep_hour", "half_hour_bin",
    "is_weekend", "is_peak_hour", "UniqueCarrier", "Origin", "Dest", "Distance",
    "departure_density_30m", "relative_density", "origin_hour_hist_taxi",
    "route_hist_taxi", "carrier_origin_hist_taxi", "origin_hour_hist_n",
    "route_hist_n", "TaxiOut",
]


def enhanced_sample(condition, fraction, limit_n, seed):
    return (
        features_enhanced.filter(condition)
        .select(enhanced_cols)
        .sample(False, fraction, seed=seed)
        .limit(limit_n)
        .toPandas()
    )


train_v3_pd = enhanced_sample(F.col("Month") <= 9, 0.10, 450_000, 52)
valid_v3_pd = enhanced_sample(F.col("Month") == 10, 0.30, 140_000, 53)
test_v3_pd = enhanced_sample(F.col("Month") >= 11, 0.22, 180_000, 54)
print("Rows train/valid/test:", len(train_v3_pd), len(valid_v3_pd), len(test_v3_pd))

y_true = test_v3_pd["TaxiOut"].to_numpy()
baseline_metrics = pd.DataFrame([
    {
        "model": "Global mean",
        "MAE": mean_absolute_error(y_true, np.full(len(y_true), global_train_mean)),
        "RMSE": mean_squared_error(y_true, np.full(len(y_true), global_train_mean)) ** 0.5,
        "R2": r2_score(y_true, np.full(len(y_true), global_train_mean)),
    },
    {
        "model": "Origin-hour historical mean",
        "MAE": mean_absolute_error(y_true, test_v3_pd["origin_hour_hist_taxi"]),
        "RMSE": mean_squared_error(y_true, test_v3_pd["origin_hour_hist_taxi"]) ** 0.5,
        "R2": r2_score(y_true, test_v3_pd["origin_hour_hist_taxi"]),
    },
])

train_v3 = h2o.H2OFrame(train_v3_pd)
valid_v3 = h2o.H2OFrame(valid_v3_pd)
test_v3 = h2o.H2OFrame(test_v3_pd)
cat_v3 = [
    "DayofMonth", "DayOfWeek", "dep_hour", "half_hour_bin", "is_weekend",
    "is_peak_hour", "UniqueCarrier", "Origin", "Dest",
]
for col in cat_v3:
    train_v3[col] = train_v3[col].asfactor()
    valid_v3[col] = valid_v3[col].asfactor()
    test_v3[col] = test_v3[col].asfactor()

x_v3 = [c for c in enhanced_cols if c != "TaxiOut"]
aml_v3 = H2OAutoML(
    max_runtime_secs=240,
    max_models=15,
    seed=52,
    sort_metric="RMSE",
    stopping_metric="RMSE",
    project_name="taxiout_enhanced_v3",
)
aml_v3.train(
    x=x_v3,
    y="TaxiOut",
    training_frame=train_v3,
    validation_frame=valid_v3,
    leaderboard_frame=test_v3,
)

leader_v3 = aml_v3.leader
perf_v3 = leader_v3.model_performance(test_v3)
enhanced_metrics = pd.DataFrame([{
    "model": "H2O AutoML enhanced",
    "MAE": perf_v3.mae(),
    "RMSE": perf_v3.rmse(),
    "R2": perf_v3.r2(),
}])
comparison = pd.concat([baseline_metrics, enhanced_metrics], ignore_index=True)
comparison["MAE_improvement_vs_global_pct"] = (
    (baseline_metrics.iloc[0]["MAE"] - comparison["MAE"])
    / baseline_metrics.iloc[0]["MAE"] * 100
)

comparison.to_csv("/kaggle/working/model_comparison_v3.csv", index=False)
aml_v3.leaderboard.as_data_frame().to_csv(
    "/kaggle/working/h2o_leaderboard_v3.csv", index=False
)
model_v3_path = h2o.save_model(
    leader_v3, path="/kaggle/working/h2o_models_v3", force=True
)
print("Best enhanced model:", leader_v3.model_id)
print("Saved:", model_v3_path)
display(comparison)
display(aml_v3.leaderboard.as_data_frame().head(10))
