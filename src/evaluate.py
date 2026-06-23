import csv
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.datasets import get_dataset_config


DEFAULT_DATE = "2022-05-01"
DATASET = "aiops2022"
DEFAULT_DATES = {
    "aiops2022": "2022-05-01",
    "nezha": "2023-01-30",
    "RCAEval": "1",
}


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument(
        "--level",
        choices=("service", "pod", "node"),
        default=None,
        help="Only evaluate labels from one aiops2022 hierarchy level.",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def normalize_service_name(value: object) -> str:
    name = normalize_text(value).strip("`'\"")
    if not name:
        return ""

    name = name.split("/", 1)[0]
    name = name.split(".", 1)[0]
    name = name.lower()

    if name.startswith("ts-"):
        name = name[3:]
    if name.endswith("-service"):
        name = name[:-8]

    parts = name.split("-")
    if len(parts) >= 3 and all(char in "0123456789abcdef" for char in parts[-2]) and len(parts[-1]) == 5:
        name = "-".join(parts[:-2])
    if name.startswith("ts-"):
        name = name[3:]
    if name.endswith("-service"):
        name = name[:-8]

    return name


def normalizer_for_dataset(dataset: str):
    if dataset in {"RCAEval", "nezha"}:
        return normalize_service_name
    return normalize_text


def load_predictions(output_csv_path: Path) -> dict[str, list[str]]:
    predictions: dict[str, list[str]] = {}
    with output_csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            timestamp = normalize_text(row.get("timestamp"))
            topk: list[str] = []
            for index in range(1, 6):
                topk.append(normalize_text(row.get(f"location{index}")))
            predictions[timestamp] = topk
    return predictions


def load_labels(labels_csv_path: Path) -> list[dict[str, str]]:
    with labels_csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return [
            {
                "timestamp": normalize_text(row.get("timestamp")),
                "level": normalize_text(row.get("level")),
                "location": normalize_text(row.get("cmdb_id") or row.get("location")),
            }
            for row in csv.DictReader(csv_file)
        ]


def reciprocal_rank_location(
    predictions: list[str],
    true_location: str,
    normalize_location,
) -> float:
    normalized_true_location = normalize_location(true_location)
    for rank, location in enumerate(predictions, start=1):
        if normalize_location(location) == normalized_true_location:
            return 1.0 / rank
    return 0.0


def compute_metrics(
    labels: list[dict[str, str]],
    predictions_by_timestamp: dict[str, list[str]],
    normalize_location=normalize_text,
) -> dict[str, float]:
    total = len(labels)
    if total == 0:
        raise ValueError("No labels found for evaluation.")

    acc1_hits = 0
    acc3_hits = 0
    acc5_hits = 0
    location_rr_sum = 0.0

    for label in labels:
        true_location = label["location"]
        normalized_true_location = normalize_location(true_location)
        predictions = predictions_by_timestamp.get(label["timestamp"], [])
        normalized_predictions = [normalize_location(location) for location in predictions]

        if normalized_true_location in normalized_predictions[:1]:
            acc1_hits += 1
        if normalized_true_location in normalized_predictions[:3]:
            acc3_hits += 1
        if normalized_true_location in normalized_predictions[:5]:
            acc5_hits += 1

        location_rr_sum += reciprocal_rank_location(predictions, true_location, normalize_location)

    return {
        "Acc@1": acc1_hits / total,
        "Acc@3": acc3_hits / total,
        "Acc@5": acc5_hits / total,
        "MRR": location_rr_sum / total,
    }


def resolve_date(dataset: str, date: str | None) -> str:
    if date:
        return date
    return DEFAULT_DATES.get(dataset, DEFAULT_DATE)


def resolve_output_csv_path(root: Path, dataset: str, date: str) -> Path:
    candidates = [
        root / "outputs" / dataset / date / "output.csv",
        root / "src" / "output" / dataset / date / "output.csv",
        root / "src" / "output" / date / "output.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = "\n".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Output CSV not found. Searched:\n{searched}")


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    date = resolve_date(dataset, args.date)

    root = PROJECT_ROOT

    output_csv_path = resolve_output_csv_path(root, dataset, date)

    labels_csv_path = root / get_dataset_config(dataset).processed_root / str(date) / "labels.csv"

    predictions_by_timestamp = load_predictions(output_csv_path)
    labels = load_labels(labels_csv_path)
    if args.level:
        labels = [label for label in labels if label.get("level") == args.level]
    metrics = compute_metrics(labels, predictions_by_timestamp, normalizer_for_dataset(dataset))

    level_suffix = f" ({args.level} level)" if args.level else ""
    print(f"Evaluation for {dataset}/{date}{level_suffix}")
    print(f"Samples: {len(labels)}")
    for metric_name, value in metrics.items():
        print(f"{metric_name}: {value:.4f}")


if __name__ == "__main__":
    main()
