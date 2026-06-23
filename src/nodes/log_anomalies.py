import re
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from config.log_keyword import LOG_KEYWORDS
from ..datasets import get_dataset_config

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def _load_log_dataframe(date: str, start_timestamp: int | str, dataset: str | None = None) -> pd.DataFrame:
    """Load log rows from the normal window and fault window."""
    dataset_config = get_dataset_config(dataset)
    log_path = (
        dataset_config.processed_root
        / str(date)
        / "log"
        / "log_filebeat-testbed-log-service.csv"
    )
    log_df = pd.read_csv(log_path)

    log_df["timestamp"] = pd.to_numeric(log_df["timestamp"], errors="coerce")
    log_df = log_df.dropna(subset=["timestamp"]).copy()
    log_df["timestamp"] = log_df["timestamp"].astype("int64")

    start_timestamp = int(start_timestamp)
    normal_start_timestamp = start_timestamp - dataset_config.normal_window_steps * 60
    end_timestamp = start_timestamp + dataset_config.fault_window_steps * 60
    log_df = log_df[
        (
            (log_df["timestamp"] > normal_start_timestamp)
            & (log_df["timestamp"] < start_timestamp)
        )
        | (
            (log_df["timestamp"] > start_timestamp)
            & (log_df["timestamp"] <= end_timestamp)
        )
    ].copy()
    log_df["log_period"] = np.where(log_df["timestamp"] < start_timestamp, "baseline", "current")
    return log_df


def _filter_log_dataframe_by_keywords(log_df: pd.DataFrame) -> pd.DataFrame:
    """Keep log rows whose value contains any configured keyword."""
    if log_df.empty:
        return log_df.copy()

    keyword_pattern = "|".join(re.escape(keyword) for keyword in LOG_KEYWORDS)
    filtered_df = log_df[
        log_df["value"].fillna("").astype(str).str.contains(keyword_pattern, case=False, regex=True)
    ].copy()

    excluded_patterns = [
        "NullPointerException",
        "EVERE: Exception while executing runnable",
        "failed to retrieve ads",
    ]
    exclusion_pattern = "|".join(re.escape(pattern) for pattern in excluded_patterns)
    return filtered_df[
        ~filtered_df["value"].fillna("").astype(str).str.contains(exclusion_pattern, case=False, regex=True)
    ].copy()


def _normalize_log_value_patterns(log_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common variable patterns in log values for downstream grouping."""
    if log_df.empty:
        return log_df.copy()

    normalized_df = log_df.copy()
    normalized_series = normalized_df["value"].fillna("").astype(str)

    replacements = [
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP>"),
        (r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "<UUID>"),
        (r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b", "<DATETIME>"),
        (r"\b\d{10,16}\b", "<LONG_NUM>"),
        (r"\b0x[0-9a-fA-F]+\b", "<HEX>"),
        (r"\b[a-f0-9]{16,64}\b", "<HASH>"),
        (r"\b(?:[A-Za-z]:)?[\\/][^\s,:;\"']+", "<PATH>"),
        (r"(?<!\S):\d{2,5}\b", ":<PORT>"),
    ]

    for pattern, replacement in replacements:
        normalized_series = normalized_series.str.replace(pattern, replacement, regex=True)

    normalized_df["value"] = normalized_series
    return normalized_df


def _cluster_log_dataframe_by_dbscan(
    log_df: pd.DataFrame,
    eps: float = 0.5,
    min_samples: int = 2,
) -> pd.DataFrame:
    """Cluster normalized log values with DBSCAN using 1 - Jaccard similarity."""
    if log_df.empty:
        clustered_df = log_df.copy()
        clustered_df["cluster_id"] = pd.Series(dtype="int64")
        return clustered_df

    clustered_df = log_df.copy()
    token_sets = [
        set(re.findall(r"<[^>]+>|[a-zA-Z0-9_]+", value.lower()))
        for value in clustered_df["value"].fillna("").astype(str)
    ]

    size = len(token_sets)
    distance_matrix = np.zeros((size, size), dtype=float)
    for i in range(size):
        for j in range(i + 1, size):
            union = token_sets[i] | token_sets[j]
            similarity = 1.0 if not union else len(token_sets[i] & token_sets[j]) / len(union)
            distance = 1.0 - similarity
            distance_matrix[i, j] = distance
            distance_matrix[j, i] = distance

    cluster_model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    clustered_df["cluster_id"] = cluster_model.fit_predict(distance_matrix)
    return clustered_df


def _summarize_log_clusters(
    clustered_log_df: pd.DataFrame,
    limit: int = 20,
    empty_message: str = "No log anomalies found.",
) -> str:
    """Summarize clustered logs into one line per cluster."""
    if clustered_log_df.empty:
        return empty_message

    working_df = clustered_log_df.copy()
    working_df["cluster_key"] = working_df["cluster_id"].astype(str)

    noise_mask = working_df["cluster_id"].eq(-1)
    if noise_mask.any():
        noise_groups = working_df.loc[noise_mask, "value"].factorize()[0]
        working_df.loc[noise_mask, "cluster_key"] = [f"noise_{idx}" for idx in noise_groups]

    summary_rows = []
    for _cluster_key, group_df in working_df.groupby("cluster_key", sort=False):
        representative_log = str(group_df.iloc[0]["value"])
        cmdb_ids = sorted({str(cmdb_id) for cmdb_id in group_df["cmdb_id"].dropna()})
        components = ", ".join(cmdb_ids) if cmdb_ids else "unknown components"
        summary_rows.append(
            (
                len(group_df),
                f'- "{representative_log}" appeared {len(group_df)} times in {components}',
            )
        )

    summary_rows.sort(key=lambda item: item[0], reverse=True)
    return "\n".join(line for _, line in summary_rows[:limit])


def log_anomalies(state: "WorkflowState") -> dict[str, Any]:
    """Build log anomalies text."""
    log_df = _load_log_dataframe(state["date"], state["start_timestamp"], state.get("dataset"))
    filtered_log_df = _filter_log_dataframe_by_keywords(log_df)
    if filtered_log_df.empty:
        return {
            "log_anomalies": "No log anomalies found.",
            "log_normal": "No normal log patterns found.",
        }

    normalized_log_df = _normalize_log_value_patterns(filtered_log_df)
    normal_log_df = normalized_log_df[normalized_log_df["log_period"] == "baseline"].copy()
    anomaly_log_df = normalized_log_df[normalized_log_df["log_period"] == "current"].copy()

    clustered_normal_log_df = _cluster_log_dataframe_by_dbscan(normal_log_df)
    clustered_anomaly_log_df = _cluster_log_dataframe_by_dbscan(anomaly_log_df)
    log_normal_text = _summarize_log_clusters(
        clustered_normal_log_df,
        empty_message="No normal log patterns found.",
    )
    log_anomalies_text = _summarize_log_clusters(clustered_anomaly_log_df)
    return {
        "log_anomalies": log_anomalies_text,
        "log_normal": log_normal_text,
    }
