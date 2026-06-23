#!/usr/bin/env python3
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GROUNDTRUTH_DIR = PROJECT_ROOT / "data" / "aiops2022" / "groundtruth"
OUTPUT_ROOT = PROJECT_ROOT / "processed_data" / "aiops2022"
REQUIRED_COLUMNS = ["timestamp", "level", "cmdb_id", "failure_type"]
FAILURE_TYPE_MAPPING = {
    "k8s容器网络丢包": "k8s容器网络故障",
    "k8s容器网络延迟": "k8s容器网络故障",
    "k8s容器网络资源包损坏": "k8s容器网络故障",
    "k8s容器网络资源包重复发送": "k8s容器网络故障",  
    "k8s容器写io负载": "k8s容器io负载",
    "k8s容器读io负载": "k8s容器io负载",
    "node 磁盘写IO消耗": "node磁盘故障",
    "node 磁盘空间消耗": "node磁盘故障",
    "node 磁盘读IO消耗": "node磁盘故障",
    "node节点CPU爬升": "node节点CPU故障",
    "node 内存消耗": "node内存消耗"
}


def find_input_files() -> list[Path]:
    input_files = sorted(list(GROUNDTRUTH_DIR.glob("groundtruth-*.json")) + list(GROUNDTRUTH_DIR.glob("groundtruth-*.csv")))
    if not input_files:
        raise FileNotFoundError(f"Could not locate any groundtruth files in {GROUNDTRUTH_DIR}")
    return input_files


def extract_date(input_file: Path) -> str:
    return input_file.stem.removeprefix("groundtruth-")


def load_groundtruth(input_file: Path) -> pd.DataFrame:
    if input_file.suffix.lower() == ".json":
        with input_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        df = pd.DataFrame(data)
    elif input_file.suffix.lower() == ".csv":
        df = pd.read_csv(input_file)
    else:
        raise ValueError(f"Unsupported file type: {input_file}")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns in {input_file}: {missing_columns}")

    result_df = df[REQUIRED_COLUMNS].copy()
    result_df["timestamp"] = pd.to_numeric(result_df["timestamp"], errors="raise").astype("int64")
    result_df["failure_type"] = (
        result_df["failure_type"].astype(str).str.strip().replace(FAILURE_TYPE_MAPPING)
    )
    return result_df


def write_labels(df: pd.DataFrame, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)


def main() -> None:
    for input_file in find_input_files():
        date_str = extract_date(input_file)
        output_file = OUTPUT_ROOT / date_str / "labels.csv"

        label_df = load_groundtruth(input_file)
        write_labels(label_df, output_file)

        print(f"Done. Output written to: {output_file}")


if __name__ == "__main__":
    main()
