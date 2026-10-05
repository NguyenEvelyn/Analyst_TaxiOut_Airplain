"""Spark ETL có thể chạy với file local, Kaggle hoặc HDFS.

Ví dụ local:
    spark-submit hdfs_spark_job.py --input airline.csv --output ./warehouse

Ví dụ HDFS:
    spark-submit hdfs_spark_job.py \
      --input hdfs://namenode:9000/airport/raw/airline.csv \
      --output hdfs://namenode:9000/airport/gold
"""

import argparse

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
    return parser.parse_args()


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("AirportTaxiTimeHDFS").getOrCreate()

    raw = (
        spark.read.option("header", True).option("inferSchema", True).csv(args.input)
        .select(*REQUIRED_COLUMNS)
    )
    clean = (
        raw.filter(F.col("Year") == args.year)
        .filter((F.col("Cancelled") == 0) & (F.col("Diverted") == 0))
        .filter(F.col("TaxiOut").between(1, 180))
        .withColumn("flight_date", F.make_date("Year", "Month", "DayofMonth"))
        .withColumn("dep_hour", (F.floor(F.col("CRSDepTime") / 100) % 24).cast("int"))
        .withColumn("dep_minute", (F.col("CRSDepTime") % 100).cast("int"))
        .filter(F.col("dep_minute").between(0, 59))
        .withColumn("half_hour_bin", (
            F.floor((F.col("dep_hour") * 60 + F.col("dep_minute")) / 30) * 30
        ).cast("int"))
    )

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
    print("Clean rows:", clean.count())
    print("Output:", args.output)
    spark.stop()


if __name__ == "__main__":
    main()
