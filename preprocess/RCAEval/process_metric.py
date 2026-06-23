#!/usr/bin/env python3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from common import normalize_service_name, read_inject_time, split_run_contexts_by_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "RCAEval"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "RCAEval"
METRIC_FILE_NAME = "simple_metrics.csv"
MINUTES_BEFORE = 10
MINUTES_AFTER = 5
SKIP_METRICS = {"mem", "diskio", "workload"}


def parse_metric_column(column: str) -> tuple[str, str] | None:
    if "_" not in column:
        return None
    service_name, metric_name = column.split("_", 1)
    return normalize_service_name(service_name), metric_name.strip()


def sample_by_injection_minute(metric_df: pd.DataFrame, inject_time: int) -> pd.DataFrame:
    required_timestamps = [inject_time + offset * 60 for offset in range(-MINUTES_BEFORE, MINUTES_AFTER + 1)]
    metric_df = metric_df.copy()
    metric_df["time"] = pd.to_numeric(metric_df["time"], errors="coerce")
    metric_df = metric_df.dropna(subset=["time"]).copy()
    metric_df["time"] = metric_df["time"].astype("int64")
    metric_df = metric_df.set_index("time").sort_index()

    sampled_df = metric_df.reindex(required_timestamps, method="nearest", tolerance=30)
    sampled_df.insert(0, "timestamp", required_timestamps)
    return sampled_df.reset_index(drop=True)


def append_run_metrics(run_dir: Path, service_frames: dict[str, list[pd.DataFrame]]) -> None:
    metric_file = run_dir / METRIC_FILE_NAME
    if not metric_file.exists():
        raise FileNotFoundError(f"Metric file not found: {metric_file}")

    inject_time = read_inject_time(run_dir)
    sampled_df = sample_by_injection_minute(pd.read_csv(metric_file), inject_time)

    service_columns: dict[str, dict[str, str]] = defaultdict(dict)
    for column in sampled_df.columns:
        if column == "timestamp":
            continue
        parsed = parse_metric_column(column)
        if parsed is None:
            continue
        service_name, metric_name = parsed
        if "-mongo" in service_name:
            continue
        if metric_name in SKIP_METRICS:
            continue
        service_columns[service_name][metric_name] = column

    for service_name, metric_columns in service_columns.items():
        output_df = sampled_df[["timestamp", *metric_columns.values()]].copy()
        output_df = output_df.rename(columns={source: metric for metric, source in metric_columns.items()})
        for column in output_df.columns:
            if column != "timestamp":
                output_df[column] = pd.to_numeric(output_df[column], errors="coerce")
        service_frames[service_name].append(output_df)


def write_metric_outputs(output_date: str, run_contexts) -> None:
    service_frames: dict[str, list[pd.DataFrame]] = defaultdict(list)
    for context in run_contexts:
        append_run_metrics(context.run_dir, service_frames)

    output_dir = OUTPUT_ROOT / output_date / "metric"
    output_dir.mkdir(parents=True, exist_ok=True)

    for service_name, frames in sorted(service_frames.items()):
        service_df = pd.concat(frames, ignore_index=True)
        service_df = service_df.groupby("timestamp", as_index=False).mean(numeric_only=True)
        service_df = service_df.sort_values("timestamp")
        service_df.to_csv(output_dir / f"{service_name}.csv", index=False)

    print(f"Done. Output written to: {output_dir}")


def main() -> None:
    for output_date, run_contexts in split_run_contexts_by_date(SOURCE_ROOT).items():
        write_metric_outputs(output_date, run_contexts)


if __name__ == "__main__":
    main()
