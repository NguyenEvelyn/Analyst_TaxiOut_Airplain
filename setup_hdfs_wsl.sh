#!/usr/bin/env bash
set -euo pipefail

# Development-only, single-node HDFS inside the user's Ubuntu WSL distribution.
HADOOP_VERSION=3.5.0
ARCHIVE_URL="https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz"
ARCHIVE_SHA512=04ab94496cc00c8b7a28d03f6308eff8d2a4e7f37a9da5e8e086e4d6fc990e7a94d661908f6a6136039536efb362614b8aecdef185b5fb8ed588f0b152c7aa16
HADOOP_DIR="$HOME/hadoop-${HADOOP_VERSION}"
ARCHIVE_PATH="$HOME/hadoop-${HADOOP_VERSION}.tar.gz"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -un)" != "phuonguyen" ]; then
  echo "This configuration is for /home/phuonguyen. Adjust hadoop-config first." >&2
  exit 1
fi

if [ ! -d "$HADOOP_DIR" ]; then
  if [ ! -f "$ARCHIVE_PATH" ] || ! printf '%s  %s\n' "$ARCHIVE_SHA512" "$ARCHIVE_PATH" | sha512sum --check --status; then
    curl --fail --location --continue-at - --retry 10 --retry-all-errors \
      --retry-delay 3 --no-progress-meter --output "$ARCHIVE_PATH" "$ARCHIVE_URL"
  fi
  printf '%s  %s\n' "$ARCHIVE_SHA512" "$ARCHIVE_PATH" | sha512sum --check --status
  tar -xzf "$ARCHIVE_PATH" -C "$HOME"
fi

cp "$PROJECT_DIR/hadoop-config/core-site.xml" "$HADOOP_DIR/etc/hadoop/core-site.xml"
cp "$PROJECT_DIR/hadoop-config/hdfs-site.xml" "$HADOOP_DIR/etc/hadoop/hdfs-site.xml"

export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
export HADOOP_HOME="$HADOOP_DIR"
export HADOOP_CONF_DIR="$HADOOP_DIR/etc/hadoop"
export PATH="$HADOOP_DIR/bin:$PATH"
mkdir -p "$HOME/hadoop-data"

NAME_DIR="$HOME/hadoop-data/namenode"
if [ ! -f "$NAME_DIR/current/VERSION" ]; then
  if [ -d "$NAME_DIR" ] && [ -n "$(find "$NAME_DIR" -mindepth 1 -print -quit)" ]; then
    echo "NameNode directory contains data but no VERSION marker; refusing to format." >&2
    exit 1
  fi
  hdfs namenode -format -nonInteractive
fi

start_daemon_if_needed() {
  local daemon="$1"
  local pid_file="/tmp/hadoop-$(id -un)-${daemon}.pid"
  local pid=""

  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file")"
  fi
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "${daemon} is already running as process ${pid}."
    return
  fi

  # A PID file without a live process is stale and prevents Hadoop restarting.
  if [ -f "$pid_file" ]; then
    rm -f "$pid_file"
  fi
  hdfs --daemon start "$daemon"
}

start_daemon_if_needed namenode
start_daemon_if_needed datanode

# The Java process can exist a few seconds before the NameNode RPC port is ready.
for attempt in $(seq 1 30); do
  if hdfs dfsadmin -report >/tmp/hdfs-dfsadmin-report.txt 2>/tmp/hdfs-dfsadmin-error.txt; then
    cat /tmp/hdfs-dfsadmin-report.txt
    echo "HDFS ready at hdfs://127.0.0.1:9000"
    exit 0
  fi
  sleep 1
done

echo "HDFS processes started but did not become ready after 30 seconds." >&2
cat /tmp/hdfs-dfsadmin-error.txt >&2
exit 1
