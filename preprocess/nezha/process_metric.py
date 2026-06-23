#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd

from common import default_dates, normalize_service_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "nezha"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "nezha"
KEPT_METRIC_COLUMNS = (
    "CpuUsageRate(%)",
    "PodSuccessRate(%)",
    "SuccessRate(%)",
    "MemoryUsageRate(%)",
)


def output_name(metric_file: Path, df: pd.DataFrame) -> str:
    if "PodName" in df.columns and not df["PodName"].dropna().empty:
        return f"{normalize_service_name(df['PodName'].dropna().iloc[0])}.csv"
    if "ServiceName" in df.columns and not df["ServiceName"].dropna().empty:
        return f"{normalize_service_name(df['ServiceName'].dropna().iloc[0])}.csv"
    return f"{normalize_service_name(metric_file.stem.removesuffix('_metric'))}.csv"


def process_one_file(metric_file: Path, output_dir: Path) -> None:
    df = pd.read_csv(metric_file)
    if "TimeStamp" not in df.columns:
        raise ValueError(f"Missing TimeStamp column in {metric_file}")

    result_df = df.copy()
    result_df = result_df.rename(columns={"TimeStamp": "timestamp"})
    drop_columns = [column for column in ("Time", "PodName", "ServiceName") if column in result_df.columns]
    result_df = result_df.drop(columns=drop_columns)

    kept_columns = [column for column in KEPT_METRIC_COLUMNS if column in result_df.columns]
    result_df = result_df[["timestamp", *kept_columns]]
    result_df["timestamp"] = pd.to_numeric(result_df["timestamp"], errors="raise").astype("int64")
    result_df = result_df.sort_values("timestamp")

    for column in result_df.columns:
        if column != "timestamp":
            result_df[column] = pd.to_numeric(result_df[column], errors="coerce")

    output_dir.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_dir / output_name(metric_file, df), index=False)


def process_one_date(date: str) -> None:
    input_dir = SOURCE_ROOT / date / "metric"
    if not input_dir.exists():
        raise FileNotFoundError(f"Input metric directory not found: {input_dir}")

    metric_files = sorted(input_dir.glob("*.csv"))
    if not metric_files:
        raise FileNotFoundError(f"No metric CSV files found in {input_dir}")

    output_dir = OUTPUT_ROOT / date / "metric"
    for metric_file in metric_files:
        process_one_file(metric_file, output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Nezha metric files into component CSV files.")
    parser.add_argument("dates", nargs="*", help="Date folders to process. Defaults to all dates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dates = args.dates or default_dates(SOURCE_ROOT)
    for date in dates:
        process_one_date(date)
    print(f"Done. Output written to: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
