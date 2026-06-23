from __future__ import annotations

import csv
import sys
from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from src.datasets import get_dataset_config
from src.workflow import build_workflow

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

DEFAULT_DATE = "2022-05-05"
DEFAULT_DATASET = "aiops2022"
DEFAULT_PARALLEL_WORKERS = 1
DEFAULT_OUTPUT_DIRNAME = "outputs"
DEFAULT_ARTIFACT_DIRNAME = "artifacts"


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Run EviFlow RCA inference.")
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--parallel-workers", type=int, default=DEFAULT_PARALLEL_WORKERS)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIRNAME,
        help="Directory used for generated RCA predictions.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=DEFAULT_ARTIFACT_DIRNAME,
        help="Directory used for optional workflow visualization artifacts.",
    )
    parser.add_argument(
        "--export-graph",
        action="store_true",
        help="Export workflow graph artifacts to the artifact directory.",
    )
    return parser.parse_args()


def export_workflow_graph(app: Any, artifact_dir: Path) -> None:
    graph_view = app.get_graph()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    mermaid_path = artifact_dir / "workflow_graph.mmd"
    mermaid_path.write_text(graph_view.draw_mermaid(), encoding="utf-8")

    try:
        (artifact_dir / "workflow_graph.png").write_bytes(graph_view.draw_mermaid_png())
    except Exception:
        return


def build_output_row(timestamp: str, rca_result: dict[str, Any]) -> dict[str, str]:
    root_causes = rca_result.get("root_causes", []) if isinstance(rca_result, dict) else []
    row = {"timestamp": timestamp}
    for index in range(5):
        item = root_causes[index] if index < len(root_causes) and isinstance(root_causes[index], dict) else {}
        row[f"location{index + 1}"] = str(item.get("location", "")).strip()
    return row


def build_output_fieldnames() -> list[str]:
    return ["timestamp", *(f"location{index}" for index in range(1, 6))]


def output_dir_for_dataset(output_root: Path, dataset: str, date: str) -> Path:
    return output_root / dataset / date


def build_initial_state(dataset: str, date: str, timestamp: str) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "date": date,
        "start_timestamp": int(timestamp),
    }


def run_single_iteration(dataset: str, date: str, timestamp: str) -> tuple[str, dict[str, Any]]:
    app = build_workflow()
    result = app.invoke(build_initial_state(dataset, date, timestamp))
    return timestamp, result.get("rca_result", {})


def run_workflow_sequential(
    rows: list[dict[str, str]],
    dataset: str,
    date: str,
    export_graph: bool,
    artifact_dir: Path,
) -> list[dict[str, str]]:
    app = build_workflow()
    if export_graph:
        export_workflow_graph(app, artifact_dir)

    output_rows: list[dict[str, str]] = []
    if tqdm is None:
        for row in rows:
            result = app.invoke(build_initial_state(dataset, date, row["timestamp"]))
            output_rows.append(build_output_row(row["timestamp"], result.get("rca_result", {})))
        return output_rows

    with tqdm(rows, desc=date, unit="case") as progress:
        for row in progress:
            result = app.invoke(build_initial_state(dataset, date, row["timestamp"]))
            output_rows.append(build_output_row(row["timestamp"], result.get("rca_result", {})))

    return output_rows


def run_workflow_parallel(
    rows: list[dict[str, str]],
    dataset: str,
    date: str,
    max_workers: int,
    export_graph: bool,
    artifact_dir: Path,
) -> list[dict[str, str]]:
    if export_graph:
        export_workflow_graph(build_workflow(), artifact_dir)

    indexed_rows = list(enumerate(rows, start=1))
    results_by_index: dict[int, dict[str, str]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {
            executor.submit(run_single_iteration, dataset, date, row["timestamp"]): index
            for index, row in indexed_rows
        }

        if tqdm is None:
            for future in as_completed(future_to_item):
                index = future_to_item[future]
                timestamp, rca_result = future.result()
                results_by_index[index] = build_output_row(timestamp, rca_result)
        else:
            with tqdm(total=len(indexed_rows), desc=date, unit="case") as progress:
                for future in as_completed(future_to_item):
                    index = future_to_item[future]
                    timestamp, rca_result = future.result()
                    results_by_index[index] = build_output_row(timestamp, rca_result)
                    progress.update(1)

    return [results_by_index[index] for index, _row in indexed_rows]


def load_case_rows(label_csv_path: Path, max_cases: int) -> list[dict[str, str]]:
    with label_csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    if max_cases > 0:
        return rows[:max_cases]
    return rows


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    date = args.date
    parallel_workers = max(1, args.parallel_workers)

    sys.stdout.write(f"Dataset: {dataset}\nDate: {date}\n")
    sys.stdout.flush()

    root = Path(__file__).resolve().parent
    label_csv_path = root / get_dataset_config(dataset).processed_root / str(date) / "labels.csv"
    output_root = root / args.output_dir
    artifact_dir = root / args.artifact_dir
    output_dir = output_dir_for_dataset(output_root, dataset, date)
    output_csv_path = output_dir / "output.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_case_rows(label_csv_path, args.max_cases)

    if parallel_workers > 1:
        output_rows = run_workflow_parallel(
            rows,
            dataset,
            date,
            parallel_workers,
            export_graph=args.export_graph,
            artifact_dir=artifact_dir,
        )
    else:
        output_rows = run_workflow_sequential(
            rows,
            dataset,
            date,
            export_graph=args.export_graph,
            artifact_dir=artifact_dir,
        )

    with output_csv_path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=build_output_fieldnames())
        writer.writeheader()
        writer.writerows(output_rows)


if __name__ == "__main__":
    main()
