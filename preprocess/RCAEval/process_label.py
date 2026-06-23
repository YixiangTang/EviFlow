#!/usr/bin/env python3
from pathlib import Path

import pandas as pd

from common import parse_case_name, read_inject_time, split_run_contexts_by_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "data" / "RCAEval"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "RCAEval"


def load_label_rows(run_contexts) -> list[dict[str, object]]:
    rows = []
    for context in run_contexts:
        service_name, failure_type = parse_case_name(context.case_dir)
        rows.append(
            {
                "timestamp": read_inject_time(context.run_dir),
                "level": "service",
                "cmdb_id": service_name,
                "failure_type": failure_type,
            }
        )
    rows.sort(key=lambda row: (int(row["timestamp"]), str(row["cmdb_id"]), str(row["failure_type"])))
    return rows


def main() -> None:
    for output_date, run_contexts in split_run_contexts_by_date(SOURCE_ROOT).items():
        output_file = OUTPUT_ROOT / output_date / "labels.csv"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(load_label_rows(run_contexts), columns=["timestamp", "level", "cmdb_id", "failure_type"]).to_csv(
            output_file,
            index=False,
        )
        print(f"Done. Output written to: {output_file}")


if __name__ == "__main__":
    main()
