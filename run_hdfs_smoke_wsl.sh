#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
export HADOOP_HOME="$HOME/hadoop-3.5.0"
export HADOOP_CONF_DIR="$HADOOP_HOME/etc/hadoop"
export PYSPARK_PYTHON="$HOME/bigdata-venv/bin/python"
export SPARK_LOCAL_IP=127.0.0.1
export PATH="$HADOOP_HOME/bin:$HOME/bigdata-venv/bin:$PATH"

if ! hdfs dfsadmin -report >/dev/null 2>&1; then
  echo "HDFS is not running. Run: bash setup_hdfs_wsl.sh in this Ubuntu session." >&2
  exit 1
fi
hdfs dfsadmin -safemode wait
hdfs dfs -mkdir -p /airport/raw/smoke
hdfs dfs -put -f - /airport/raw/smoke/flights_smoke.csv < "$PROJECT_DIR/fixtures/flights_smoke.csv"
run_id="$(date +%s)"
output_uri="hdfs://127.0.0.1:9000/airport/gold/smoke-${run_id}"
spark-submit --master 'local[2]' --driver-memory 2g \
  "$PROJECT_DIR/hdfs_spark_job.py" \
  --input hdfs://127.0.0.1:9000/airport/raw/smoke/flights_smoke.csv \
  --output "$output_uri"

hdfs dfs -ls "$output_uri"
echo "HDFS_SPARK_SMOKE_OUTPUT=$output_uri"
