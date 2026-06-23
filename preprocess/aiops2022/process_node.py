#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.metrics import node_metrics


SOURCE_ROOT = PROJECT_ROOT / "data" / "aiops2022"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "aiops2022"
KEEP_METRICS = set(node_metrics)
DEFAULT_INPUT_FILES = [
    SOURCE_ROOT / "2022-05-01" / "cloudbed" / "metric" / "node" / "kpi_cloudbed1_metric_0324.csv",
    SOURCE_ROOT / "2022-05-03" / "cloudbed" / "metric" / "node" / "kpi_cloudbed2_metric_0324.csv",
    SOURCE_ROOT / "2022-05-05" / "cloudbed" / "metric" / "node" / "kpi_cloudbed2_metric_0325.csv",
    SOURCE_ROOT / "2022-05-07" / "cloudbed" / "metric" / "node" / "kpi_cloudbed3_metric_0325.csv",
    SOURCE_ROOT / "2022-05-09" / "cloudbed" / "metric" / "node" / "kpi_cloudbed1_metric_0315.csv",
]


def sort_timestamp(ts: str):
    try:
        return int(ts)
    except ValueError:
        return ts


def extract_date_folder(input_file: Path) -> str:
    for part in input_file.parts:
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            return part
    raise ValueError(f"Cannot infer date folder from path: {input_file}")


def split_one_csv(input_file: Path, base_output_dir: Path) -> None:
    metric_df = pd.read_csv(input_file)
    required_fields = {"timestamp", "cmdb_id", "kpi_name", "value"}
    if not required_fields.issubset(metric_df.columns):
        raise ValueError(
            f"Input CSV must contain columns: timestamp, cmdb_id, kpi_name, value. File: {input_file}"
        )

    metric_df = metric_df.loc[
        metric_df["kpi_name"].isin(KEEP_METRICS),
        ["timestamp", "cmdb_id", "kpi_name", "value"],
    ].copy()
    metric_df["value"] = pd.to_numeric(metric_df["value"], errors="coerce")
    metric_df = metric_df.dropna(subset=["timestamp", "cmdb_id", "kpi_name", "value"])
    metric_df = metric_df.groupby(["cmdb_id", "timestamp", "kpi_name"], as_index=False)["value"].mean()

    date_folder = extract_date_folder(input_file)
    output_dir = base_output_dir / date_folder / "metric" / "node"
    output_dir.mkdir(parents=True, exist_ok=True)

    for cmdb_id, component_df in metric_df.groupby("cmdb_id", sort=False):
        columns = sorted(component_df["kpi_name"].unique().tolist())
        wide_df = component_df.pivot(index="timestamp", columns="kpi_name", values="value").reset_index()
        wide_df.columns.name = None
        wide_df = wide_df.sort_values("timestamp", key=lambda series: series.map(sort_timestamp))

        output_file = output_dir / f"{cmdb_id}.csv"
        with output_file.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", *columns])
            for _, row in wide_df.iterrows():
                writer.writerow([row["timestamp"]] + [row.get(column, "") for column in columns])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split node KPI CSV files by cmdb_id and pivot kpi_name into columns."
    )
    parser.add_argument(
        "input_files",
        nargs="*",
        help="Paths to input CSV files. If omitted, the default node files are processed.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(OUTPUT_ROOT),
        help="Base directory for generated CSV files.",
    )
    args = parser.parse_args()

    input_files = [Path(path) for path in args.input_files] if args.input_files else DEFAULT_INPUT_FILES
    base_output_dir = Path(args.output_dir)
    base_output_dir.mkdir(parents=True, exist_ok=True)

    for input_file in input_files:
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        split_one_csv(input_file, base_output_dir)

    print(f"Done. Output written to: {base_output_dir}")


if __name__ == "__main__":
    main()
