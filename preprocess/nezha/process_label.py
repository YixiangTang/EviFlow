#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from common import default_dates, normalize_service_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "nezha"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "nezha"


def timestamp_from_inject_time(value: str) -> int:
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def load_fault_rows(fault_file: Path) -> list[dict[str, object]]:
    with fault_file.open("r", encoding="utf-8") as file:
        data = json.load(file)

    rows = []
    for hour_cases in data.values():
        for item in hour_cases:
            rows.append(
                {
                    "timestamp": timestamp_from_inject_time(str(item["inject_time"])),
                    "level": "pod",
                    "cmdb_id": normalize_service_name(item["inject_pod"]),
                    "failure_type": str(item["inject_type"]).strip(),
                }
            )
    rows.sort(key=lambda row: (row["timestamp"], row["cmdb_id"], row["failure_type"]))
    return rows[1:] if rows else rows


def process_one_date(date: str) -> None:
    fault_file = SOURCE_ROOT / date / f"{date}-fault_list.json"
    if not fault_file.exists():
        raise FileNotFoundError(f"Fault list not found: {fault_file}")

    output_file = OUTPUT_ROOT / date / "labels.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(load_fault_rows(fault_file), columns=["timestamp", "level", "cmdb_id", "failure_type"]).to_csv(
        output_file,
        index=False,
    )
    print(f"Done. Output written to: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Nezha fault lists into labels.csv files.")
    parser.add_argument("dates", nargs="*", help="Date folders to process. Defaults to all dates.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dates = args.dates or default_dates(SOURCE_ROOT)
    for date in dates:
        process_one_date(date)


if __name__ == "__main__":
    main()
