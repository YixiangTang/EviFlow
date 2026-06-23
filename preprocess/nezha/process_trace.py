#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd

from common import default_dates, normalize_service_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "nezha"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "nezha"
OUTPUT_COLUMNS = [
    "timestamp",
    "cmdb_id",
    "span_id",
    "trace_id",
    "duration",
    "type",
    "status_code",
    "operation_name",
    "parent_span",
]


def infer_span_type(operation_name: object) -> str:
    text = str(operation_name)
    if text.startswith("/") or text.upper().startswith("HTTP "):
        return "http"
    return "rpc"


def convert_trace_df(df: pd.DataFrame, input_file: Path) -> pd.DataFrame:
    required = {
        "TraceID",
        "SpanID",
        "ParentID",
        "PodName",
        "OperationName",
        "StartTimeUnixNano",
        "Duration",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing trace columns in {input_file}: {sorted(missing)}")

    result_df = pd.DataFrame()
    start_ns = pd.to_numeric(df["StartTimeUnixNano"], errors="coerce")
    result_df["timestamp"] = (start_ns // 1_000_000).astype("Int64")
    result_df["cmdb_id"] = df["PodName"].map(normalize_service_name)
    result_df["span_id"] = df["SpanID"].astype(str).str.strip()
    result_df["trace_id"] = df["TraceID"].astype(str).str.strip()
    result_df["duration"] = pd.to_numeric(df["Duration"], errors="coerce").fillna(0).astype("int64")
    result_df["type"] = df["OperationName"].map(infer_span_type)
    result_df["status_code"] = 0
    result_df["operation_name"] = df["OperationName"].astype(str).str.strip()
    result_df["parent_span"] = df["ParentID"].astype(str).str.strip().replace({"root": ""})
    result_df = result_df.dropna(subset=["timestamp"])
    result_df["timestamp"] = result_df["timestamp"].astype("int64")
    return result_df[OUTPUT_COLUMNS]


def process_one_date(date: str) -> None:
    input_dir = SOURCE_ROOT / date / "trace"
    if not input_dir.exists():
        raise FileNotFoundError(f"Input trace directory not found: {input_dir}")

    trace_files = sorted(input_dir.glob("*.csv"))
    if not trace_files:
        raise FileNotFoundError(f"No trace CSV files found in {input_dir}")

    output_file = OUTPUT_ROOT / date / "trace" / "trace_jaeger-span.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    first_write = True
    for trace_file in trace_files:
        trace_df = convert_trace_df(pd.read_csv(trace_file), trace_file)
        trace_df.to_csv(output_file, mode="w" if first_write else "a", header=first_write, index=False)
        first_write = False

    print(f"Done. Output written to: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Nezha trace files into trace_jaeger-span.csv files.")
    parser.add_argument("dates", nargs="*", help="Date folders to process. Defaults to all dates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dates = args.dates or default_dates(SOURCE_ROOT)
    for date in dates:
        process_one_date(date)


if __name__ == "__main__":
    main()
