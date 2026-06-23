import math
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..datasets import get_dataset_config

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def _get_time_factor(index: int) -> float:
    # return 1.0 / math.pow(index, 2)
    return 1.0 / math.log(1.0 + index)


def _load_metric_dataframe(
    date: str,
    start_timestamp: int | str,
    grouped: bool = False,
    dataset: str | None = None,
) -> dict[str, pd.DataFrame] | dict[str, dict[str, pd.DataFrame]]:
    """Load metric dataframes from the normal window through the fault window."""
    dataset_config = get_dataset_config(dataset)
    metric_root = dataset_config.processed_root / str(date) / "metric"
    start_timestamp = int(start_timestamp)
    window_start = start_timestamp - dataset_config.normal_window_steps * 60
    window_end = start_timestamp + dataset_config.fault_window_steps * 60

    component_groups = {
        group_name: list(components)
        for group_name, components in dataset_config.metric_components.items()
    }
    for group_name in dataset_config.grouped_metric_layers:
        if component_groups.get(group_name):
            continue
        group_dir = metric_root / group_name
        search_dir = group_dir if group_dir.exists() else metric_root
        component_groups[group_name] = sorted(file_path.stem for file_path in search_dir.glob("*.csv"))

    if grouped:
        metric_dataframes_by_group: dict[str, dict[str, pd.DataFrame]] = {
            group_name: {} for group_name in dataset_config.grouped_metric_layers
        }
    else:
        metric_dataframes: dict[str, pd.DataFrame] = {}

    for group_name, components in component_groups.items():
        group_dir = metric_root / group_name
        search_dir = group_dir if group_dir.exists() else metric_root
        for component in components:
            metric_path = search_dir / f"{component}.csv"
            if not metric_path.exists():
                continue
            metric_df = pd.read_csv(metric_path)
            metric_df["timestamp"] = pd.to_numeric(metric_df["timestamp"], errors="coerce")
            metric_df = metric_df.dropna(subset=["timestamp"]).copy()
            metric_df["timestamp"] = metric_df["timestamp"].astype("int64")
            filtered_metric_df = metric_df[
                (metric_df["timestamp"] > window_start)
                & (metric_df["timestamp"] <= window_end)
            ].copy()
            if grouped:
                metric_dataframes_by_group[group_name][component] = filtered_metric_df
            else:
                metric_dataframes[component] = filtered_metric_df

    if grouped:
        return metric_dataframes_by_group
    return metric_dataframes


def _metric_anomaly_detection(
    metric_dataframes: dict[str, dict[str, pd.DataFrame]],
    start_timestamp: int | str,
    normal_window_steps: int,
    fault_window_steps: int,
    min_output_score: float,
) -> list[dict[str, Any]]:
    """Detect metric anomalies and return a globally ranked flat list."""
    start_timestamp = int(start_timestamp)
    metric_anomalies: list[dict[str, Any]] = []
    max_anomaly_score = sum(_get_time_factor(index) for index in range(1, fault_window_steps + 1))
    min_required_rows = normal_window_steps + fault_window_steps

    for group_name, group_metric_dataframes in metric_dataframes.items():
        for component, metric_df in group_metric_dataframes.items():
            metric_columns = [column for column in metric_df.columns if column != "timestamp"]

            if metric_df.empty or len(metric_df) < min_required_rows:
                continue

            baseline_df = metric_df[metric_df["timestamp"] < start_timestamp].copy()
            current_df = metric_df[
                (metric_df["timestamp"] > start_timestamp)
                & (metric_df["timestamp"] <= start_timestamp + fault_window_steps * 60)
            ].copy().sort_values("timestamp")

            if baseline_df.empty or current_df.empty:
                continue

            for metric in metric_columns:
                baseline_series = pd.to_numeric(baseline_df[metric], errors="coerce").dropna()
                current_series = pd.to_numeric(current_df[metric], errors="coerce")

                if baseline_series.empty or current_series.dropna().empty:
                    continue

                median = baseline_series.median()
                mad = (baseline_series - median).abs().median()
                mad_scale = 1.4826 * mad + 0.5
                mad_lower = median - 3 * mad_scale
                mad_upper = median + 3 * mad_scale

                valid_current_series = current_series.dropna()
                if valid_current_series.empty:
                    continue

                mad_anomaly = (current_series < mad_lower) | (current_series > mad_upper)
                mad_anomaly = mad_anomaly.fillna(False)

                score = 0.0
                current_values = current_series.tolist()[:fault_window_steps]
                for index, (value, is_anomalous) in enumerate(
                    zip(current_values, mad_anomaly.tolist()[:fault_window_steps], strict=False),
                    start=1,
                ):
                    anomaly = 1.0 if bool(is_anomalous) else 0.0
                    if pd.isna(value):
                        extent = 0.0
                    else:
                        extent = abs(value - median) / (mad_scale * 3)
                    extent = extent / (1.0 + extent)
                    time_factor = _get_time_factor(index)
                    score += time_factor * anomaly * extent

                score = score / max_anomaly_score if max_anomaly_score > 0 else 0.0

                if score <= 0:
                    continue

                current_values_text = ", ".join(
                    "nan" if pd.isna(value) else f"{float(value):.2f}"
                    for value in current_values
                )
                if score > min_output_score:
                    metric_anomalies.append(
                        {
                            "component": component,
                            "metric": metric,
                            "score": float(score),
                            "values_text": f"[{current_values_text}]",
                            "mad_threshold": f"({float(mad_lower):.2f}, {float(mad_upper):.2f})",
                        }
                    )

    metric_anomalies.sort(
        key=lambda item: (-float(item["score"]), str(item["component"]), str(item["metric"]))
    )
    return metric_anomalies


def metric_anomalies(state: "WorkflowState") -> dict[str, Any]:
    """Build metric anomalies list."""
    dataset_config = get_dataset_config(state.get("dataset"))
    metric_dataframes = _load_metric_dataframe(
        state["date"],
        state["start_timestamp"],
        grouped=True,
        dataset=dataset_config.name,
    )
    metric_anomalies = _metric_anomaly_detection(
        metric_dataframes,
        state["start_timestamp"],
        dataset_config.normal_window_steps,
        dataset_config.fault_window_steps,
        dataset_config.min_output_score,
    )
    return {"metric_anomalies": metric_anomalies}
