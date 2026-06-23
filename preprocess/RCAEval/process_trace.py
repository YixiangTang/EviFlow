#!/usr/bin/env python3
from pathlib import Path

import pandas as pd

from common import normalize_service_name, split_run_contexts_by_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "RCAEval"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "RCAEval"
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
    if text.startswith("/") or text.upper().startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH ")):
        return "http"
    return "rpc"


def convert_trace_df(df: pd.DataFrame, input_file: Path) -> pd.DataFrame:
    required = {
        "traceID",
        "spanID",
        "parentSpanID",
        "serviceName",
        "operationName",
        "startTimeMillis",
        "duration",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing trace columns in {input_file}: {sorted(missing)}")

    start_ms = pd.to_numeric(df["startTimeMillis"], errors="coerce")

    result_df = pd.DataFrame()
    result_df["timestamp"] = start_ms
    result_df["cmdb_id"] = df["serviceName"].map(normalize_service_name)
    result_df["span_id"] = df["spanID"].astype(str).str.strip()
    result_df["trace_id"] = df["traceID"].astype(str).str.strip()
    result_df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0).astype("int64")
    result_df["type"] = df["operationName"].map(infer_span_type)
    result_df["status_code"] = pd.to_numeric(df["statusCode"], errors="coerce").fillna(0).astype("int64")
    result_df["operation_name"] = df["operationName"].astype(str).str.strip()
    result_df["parent_span"] = df["parentSpanID"].fillna("").astype(str).str.strip()
    result_df = result_df.dropna(subset=["timestamp"])
    result_df["timestamp"] = result_df["timestamp"].astype("int64")
    return result_df[OUTPUT_COLUMNS]


def iter_converted_trace_chunks(trace_file: Path):
    usecols = [
        "traceID",
        "spanID",
        "parentSpanID",
        "serviceName",
        "operationName",
        "startTimeMillis",
        "duration",
        "statusCode",
    ]
    for chunk_df in pd.read_csv(trace_file, usecols=usecols, chunksize=200_000):
        trace_df = convert_trace_df(chunk_df, trace_file)
        if not trace_df.empty:
            yield trace_df


def write_trace_output(output_date: str, run_contexts) -> None:
    output_file = OUTPUT_ROOT / output_date / "trace" / "trace_jaeger-span.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    first_write = True
    for context in run_contexts:
        trace_file = context.run_dir / "traces.csv"
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {trace_file}")
        for trace_df in iter_converted_trace_chunks(trace_file):
            trace_df.to_csv(output_file, mode="w" if first_write else "a", header=first_write, index=False)
            first_write = False

    print(f"Done. Output written to: {output_file}")


def main() -> None:
    for output_date, run_contexts in split_run_contexts_by_date(SOURCE_ROOT).items():
        write_trace_output(output_date, run_contexts)


if __name__ == "__main__":
    main()
