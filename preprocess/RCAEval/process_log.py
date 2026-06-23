#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

from common import normalize_service_name, read_inject_time, split_run_contexts_by_date


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.log_keyword import LOG_KEYWORDS


SOURCE_ROOT = PROJECT_ROOT / "data" / "RCAEval"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "RCAEval"
OUTPUT_COLUMNS = ["log_id", "timestamp", "cmdb_id", "log_name", "value"]
WINDOW_BEFORE_SECONDS = 5 * 60
WINDOW_AFTER_SECONDS = 5 * 60
KEYWORDS = tuple(keyword.lower() for keyword in LOG_KEYWORDS)


def iter_converted_log_rows(log_file: Path, inject_time: int):
    window_start = inject_time - WINDOW_BEFORE_SECONDS
    window_end = inject_time + WINDOW_AFTER_SECONDS
    with log_file.open("r", encoding="utf-8", errors="replace", newline="") as file:
        reader = csv.DictReader(file)
        missing = {"timestamp", "container_name", "message"}.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing log columns in {log_file}: {sorted(missing)}")

        for index, row in enumerate(reader):
            try:
                timestamp = int(float(row["timestamp"]) // 1_000_000_000)
            except (TypeError, ValueError):
                continue

            if timestamp < window_start:
                continue
            if timestamp > window_end:
                break

            container_name = str(row["container_name"]).strip()
            message = row.get("message", "")
            if not any(keyword in message.lower() for keyword in KEYWORDS):
                continue

            yield {
                "log_id": f"{log_file.parent.parent.name}-{log_file.parent.name}-{index}",
                "timestamp": timestamp,
                "cmdb_id": normalize_service_name(container_name),
                "log_name": container_name,
                "value": message,
            }


def write_log_output(output_date: str, run_contexts) -> None:
    output_file = OUTPUT_ROOT / output_date / "log" / "log_filebeat-testbed-log-service.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for context in run_contexts:
            log_file = context.run_dir / "logs.csv"
            if not log_file.exists():
                raise FileNotFoundError(f"Log file not found: {log_file}")
            writer.writerows(iter_converted_log_rows(log_file, read_inject_time(context.run_dir)))

    print(f"Done. Output written to: {output_file}")


def main() -> None:
    for output_date, run_contexts in split_run_contexts_by_date(SOURCE_ROOT).items():
        write_log_output(output_date, run_contexts)


if __name__ == "__main__":
    main()
