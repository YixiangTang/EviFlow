#!/usr/bin/env python3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "aiops2022"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "aiops2022"
DEFAULT_DATES = [
    "2022-05-01",
    "2022-05-03",
    "2022-05-05",
    "2022-05-07",
    "2022-05-09",
]
REQUIRED_COLUMNS = ["service", "timestamp", "rr", "sr", "mrt", "count"]
VALUE_COLUMNS = ["rr", "sr", "mrt", "count"]


def process_one_file(input_file: Path, output_dir: Path) -> None:
    df = pd.read_csv(input_file)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns in {input_file}: {missing_columns}")

    service_df = df[REQUIRED_COLUMNS].copy()
    for column in VALUE_COLUMNS:
        service_df[column] = pd.to_numeric(service_df[column], errors="coerce")
    service_df = service_df.dropna(subset=["service", "timestamp", *VALUE_COLUMNS])
    service_df = (
        service_df.groupby(["service", "timestamp"], as_index=False)[VALUE_COLUMNS]
        .mean()
        .sort_values(["service", "timestamp"])
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for service_name, one_service_df in service_df.groupby("service", sort=False):
        result_df = one_service_df[["timestamp", *VALUE_COLUMNS]].copy().sort_values("timestamp")
        result_df.to_csv(output_dir / f"{service_name}.csv", index=False)


def main() -> None:
    for date_str in DEFAULT_DATES:
        input_file = SOURCE_ROOT / date_str / "cloudbed" / "metric" / "service" / "metric_service.csv"
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        output_dir = OUTPUT_ROOT / date_str / "metric" / "service"
        process_one_file(input_file, output_dir)

    print(f"Done. Output written to: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
