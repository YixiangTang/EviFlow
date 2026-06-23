#!/usr/bin/env python3
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.metrics import pod_metrics


SOURCE_ROOT = PROJECT_ROOT / "data" / "aiops2022"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "aiops2022"
DEFAULT_DATES = [
    "2022-05-01",
    "2022-05-03",
    "2022-05-05",
    "2022-05-07",
    "2022-05-09",
]
REQUIRED_COLUMNS = ["timestamp", "cmdb_id", "value"]
KEEP_METRICS = set(pod_metrics)


def normalize_output_name(cmdb_id: str) -> str:
    parts = cmdb_id.split(".", 1)
    return parts[1] if len(parts) == 2 else cmdb_id


def kpi_name_from_file(metric_file: Path) -> str:
    return metric_file.stem.removeprefix("kpi_")


def iter_metric_files(input_dir: Path) -> list[Path]:
    return sorted(
        file_path
        for file_path in input_dir.iterdir()
        if file_path.is_file() and file_path.suffix.lower() == ".csv" and not file_path.name.startswith(".")
    )


def process_one_date(input_dir: Path, output_dir: Path) -> None:
    metric_files = iter_metric_files(input_dir)
    if not metric_files:
        raise FileNotFoundError(f"No metric CSV files found in {input_dir}")

    frames = []
    for metric_file in metric_files:
        kpi_name = kpi_name_from_file(metric_file)
        if kpi_name not in KEEP_METRICS:
            continue

        df = pd.read_csv(metric_file)
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing columns in {metric_file}: {missing_columns}")

        metric_df = df[REQUIRED_COLUMNS].copy()
        metric_df["value"] = pd.to_numeric(metric_df["value"], errors="coerce")
        metric_df = metric_df.dropna(subset=["timestamp", "cmdb_id", "value"])
        metric_df["kpi_name"] = kpi_name
        frames.append(metric_df)

    if not frames:
        raise FileNotFoundError(f"No matching pod KPI CSV files found in {input_dir}")

    merged_df = pd.concat(frames, ignore_index=True)
    merged_df = merged_df.groupby(["cmdb_id", "timestamp", "kpi_name"], as_index=False)["value"].mean()
    merged_df = merged_df.sort_values(["cmdb_id", "timestamp", "kpi_name"])
    output_dir.mkdir(parents=True, exist_ok=True)

    for cmdb_id, pod_df in merged_df.groupby("cmdb_id", sort=False):
        wide_df = (
            pod_df.pivot(index="timestamp", columns="kpi_name", values="value")
            .reset_index()
            .sort_values("timestamp")
        )
        wide_df.columns.name = None
        wide_df.to_csv(output_dir / f"{normalize_output_name(cmdb_id)}.csv", index=False)


def main() -> None:
    for date_str in DEFAULT_DATES:
        input_dir = SOURCE_ROOT / date_str / "cloudbed" / "metric" / "container"
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        output_dir = OUTPUT_ROOT / date_str / "metric" / "pod"
        process_one_date(input_dir, output_dir)

    print(f"Done. Output written to: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
