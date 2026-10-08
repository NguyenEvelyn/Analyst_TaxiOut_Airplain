"""Spark ETL có thể chạy với file local, Kaggle hoặc HDFS.

Ví dụ local:
    spark-submit hdfs_spark_job.py --input airline.csv --output ./warehouse

Ví dụ HDFS:
    spark-submit hdfs_spark_job.py \
      --input hdfs://namenode:9000/airport/raw/airline.csv \
      --output hdfs://namenode:9000/airport/gold
"""

import argparse
import time

from pyspark.sql import SparkSession, functions as F


REQUIRED_COLUMNS = [
    "Year", "Month", "DayofMonth", "DayOfWeek", "CRSDepTime",
    "UniqueCarrier", "Origin", "Dest", "Distance", "TaxiOut",
    "Cancelled", "Diverted",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Airport TaxiOut Spark ETL")
    parser.add_argument("--input", required=True, help="CSV URI: local, Kaggle hoặc hdfs://")
    parser.add_argument("--output", required=True, help="Thư mục đầu ra local hoặc hdfs://")
    parser.add_argument("--year", type=int, default=2008)
    parser.add_argument("--overwrite", action="store_true", help="Cho phép thay thế thư mục output đã có")
    parser.add_argument(
        "--skip-quality-report",
        action="store_true",
        help="Bỏ qua báo cáo đếm dữ liệu; mặc định ghi JSON vào output/data_quality_<year>",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("AirportTaxiTimeHDFS").getOrCreate()
    started = time.perf_counter()

    source = spark.read.option("header", True).option("inferSchema", True).csv(args.input)
    missing = sorted(set(REQUIRED_COLUMNS) - set(source.columns))
    if missing:
        raise ValueError(f"Input CSV thiếu cột bắt buộc: {', '.join(missing)}")
    raw = source.select(*REQUIRED_COLUMNS)
    year_data = raw.filter(F.col("Year") == args.year)
    completed = year_data.filter((F.col("Cancelled") == 0) & (F.col("Diverted") == 0))
    valid_taxi = completed.filter(F.col("TaxiOut").between(1, 180))
    with_time = (
        valid_taxi
        .withColumn("flight_date", F.make_date("Year", "Month", "DayofMonth"))
        .withColumn("dep_hour", (F.floor(F.col("CRSDepTime") / 100) % 24).cast("int"))
        .withColumn("dep_minute", (F.col("CRSDepTime") % 100).cast("int"))
        .withColumn("half_hour_bin", (
            F.floor((F.col("dep_hour") * 60 + F.col("dep_minute")) / 30) * 30
        ).cast("int"))
    )
    clean = with_time.filter(
        F.col("flight_date").isNotNull()
        & F.col("dep_hour").between(0, 23)
        & F.col("dep_minute").between(0, 59)
        & F.col("Origin").isNotNull()
        & F.col("Dest").isNotNull()
        & F.col("UniqueCarrier").isNotNull()
        & (F.col("Distance") > 0)
    ).cache()

    density = clean.groupBy("flight_date", "Origin", "half_hour_bin").agg(
        F.count("*").alias("departure_density_30m")
    )
    features = clean.join(density, ["flight_date", "Origin", "half_hour_bin"], "left")
    congestion = clean.groupBy("flight_date", "Origin", "half_hour_bin").agg(
        F.count("*").alias("flights"),
        F.round(F.avg("TaxiOut"), 2).alias("avg_taxi_out"),
        F.expr("percentile_approx(TaxiOut, 0.5)").alias("median_taxi_out"),
        F.expr("percentile_approx(TaxiOut, 0.95)").alias("p95_taxi_out"),
    )

    write_mode = "overwrite" if args.overwrite else "errorifexists"
    features.write.mode(write_mode).parquet(f"{args.output}/ml_features_{args.year}")
    congestion.write.mode(write_mode).parquet(f"{args.output}/airport_congestion_{args.year}")
    clean_rows = clean.count()
    if not args.skip_quality_report:
        counts = {
            "input_rows": raw.count(),
            "year_rows": year_data.count(),
            "completed_rows": completed.count(),
            "valid_taxi_rows": valid_taxi.count(),
            "clean_rows": clean_rows,
        }
        report = {
            "year": int(args.year),
            **counts,
            "excluded_other_year": counts["input_rows"] - counts["year_rows"],
            "excluded_cancelled_or_diverted": counts["year_rows"] - counts["completed_rows"],
            "excluded_invalid_taxiout": counts["completed_rows"] - counts["valid_taxi_rows"],
            "excluded_invalid_required_fields": counts["valid_taxi_rows"] - counts["clean_rows"],
            "spark_version": spark.version,
            "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "input_uri": args.input,
        }
        spark.createDataFrame([report]).coalesce(1).write.mode(write_mode).json(
            f"{args.output}/data_quality_{args.year}"
        )
        print("Data quality:", report)
    print("Clean rows:", clean_rows)
    print("Output:", args.output)
    spark.stop()


if __name__ == "__main__":
    main()
