#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from common import default_dates, normalize_service_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "nezha"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "nezha"
OUTPUT_COLUMNS = ["log_id", "timestamp", "cmdb_id", "log_name", "value"]


def extract_log_value(value: object) -> str:
    text = str(value)
    try:
        parsed_csv = next(csv.reader([text]))
        text = parsed_csv[0] if len(parsed_csv) == 1 else ",".join(parsed_csv)
    except csv.Error:
        text = text.strip().strip('"').replace('""', '"')

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, dict) and "log" in parsed:
        return str(parsed["log"]).rstrip()
    return text


def iter_converted_log_rows(input_file: Path) -> tuple[dict[str, object], ...]:
    rows = []
    with input_file.open("r", encoding="utf-8", errors="replace", newline="") as file:
        header = file.readline().strip().split(",", 7)
        expected = ["Timestamp", "TimeUnixNano", "Node", "PodName", "Container", "TraceID", "SpanID", "Log"]
        if header != expected:
            raise ValueError(f"Unexpected log header in {input_file}: {header}")

        for index, line in enumerate(file):
            parts = line.rstrip("\r\n").split(",", 7)
            if len(parts) != 8:
                continue
            _timestamp, time_ns, _node, pod_name, container, trace_id, span_id, log_value = parts
            try:
                timestamp = int(float(time_ns) // 1_000_000_000)
            except ValueError:
                continue
            rows.append(
                {
                    "log_id": f"{input_file.stem}-{index}-{trace_id}-{span_id}",
                    "timestamp": timestamp,
                    "cmdb_id": normalize_service_name(pod_name),
                    "log_name": container.strip(),
                    "value": extract_log_value(log_value),
                }
            )
    return tuple(rows)


def process_one_date(date: str) -> None:
    input_dir = SOURCE_ROOT / date / "log"
    if not input_dir.exists():
        raise FileNotFoundError(f"Input log directory not found: {input_dir}")

    log_files = sorted(input_dir.glob("*.csv"))
    if not log_files:
        raise FileNotFoundError(f"No log CSV files found in {input_dir}")

    output_file = OUTPUT_ROOT / date / "log" / "log_filebeat-testbed-log-service.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    first_write = True
    for log_file in log_files:
        log_df = pd.DataFrame(iter_converted_log_rows(log_file), columns=OUTPUT_COLUMNS)
        log_df.to_csv(output_file, mode="w" if first_write else "a", header=first_write, index=False)
        first_write = False

    print(f"Done. Output written to: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Nezha log files into log_filebeat-testbed-log-service.csv files.")
    parser.add_argument("dates", nargs="*", help="Date folders to process. Defaults to all dates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dates = args.dates or default_dates(SOURCE_ROOT)
    for date in dates:
        process_one_date(date)


if __name__ == "__main__":
    main()
