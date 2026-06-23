from collections import defaultdict
from typing import TYPE_CHECKING, Any

import pandas as pd

from ..datasets import get_dataset_config

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def _load_trace_dataframe(date: str, start_timestamp: int | str, dataset: str | None = None) -> pd.DataFrame:
    """Load full traces whose root span starts in the baseline or fault window."""
    dataset_config = get_dataset_config(dataset)
    trace_path = dataset_config.processed_root / str(date) / "trace" / "trace_jaeger-span.csv"
    trace_df = pd.read_csv(trace_path)

    trace_df["timestamp"] = pd.to_numeric(trace_df["timestamp"], errors="coerce")
    trace_df = trace_df.dropna(subset=["timestamp"]).copy()
    trace_df["timestamp"] = (trace_df["timestamp"] // 1000).astype("int64")

    start_timestamp = int(start_timestamp)
    baseline_start_timestamp = start_timestamp - dataset_config.normal_window_steps * 60
    end_timestamp = start_timestamp + dataset_config.fault_window_steps * 60

    root_span_df = trace_df[
        trace_df["parent_span"].isna()
        & (
            (
                (trace_df["timestamp"] > baseline_start_timestamp)
                & (trace_df["timestamp"] < start_timestamp)
            )
            | (
                (trace_df["timestamp"] > start_timestamp)
                & (trace_df["timestamp"] <= end_timestamp)
            )
        )
    ].copy()

    if root_span_df.empty:
        return trace_df.iloc[0:0].copy()

    root_trace_df = root_span_df.dropna(subset=["trace_id"])[["trace_id", "timestamp"]].rename(
        columns={"timestamp": "root_timestamp"}
    )
    root_trace_df["trace_period"] = root_trace_df["root_timestamp"].apply(
        lambda timestamp: "baseline" if timestamp < start_timestamp else "current"
    )
    root_trace_df = root_trace_df.drop_duplicates(subset=["trace_id"], keep="first")
    return trace_df.merge(root_trace_df, on="trace_id", how="inner")

def _build_trace_detail_dataframe(trace_df: pd.DataFrame) -> pd.DataFrame:
    """Attach caller information to trace spans and use duration as latency."""
    if trace_df.empty:
        return trace_df.iloc[0:0].copy()

    detail_df = trace_df.copy()
    detail_df["duration"] = pd.to_numeric(detail_df["duration"], errors="coerce")
    detail_df["status_code_numeric"] = pd.to_numeric(detail_df["status_code"], errors="coerce")
    detail_df = detail_df.dropna(subset=["trace_id", "span_id", "duration"]).copy()
    detail_df["latency"] = detail_df["duration"]

    if detail_df.empty:
        return detail_df

    caller_df = detail_df[["trace_id", "span_id", "cmdb_id", "operation_name"]].rename(
        columns={
            "span_id": "parent_span",
            "cmdb_id": "caller_cmdb_id",
            "operation_name": "caller_operation_name",
        }
    )
    return detail_df.merge(caller_df, on=["trace_id", "parent_span"], how="left")


def _format_duration_latency(duration: float) -> str:
    """Format latency in a readable string."""
    if pd.isna(duration):
        return "0us"
    if duration >= 1_000_000:
        return f"{duration / 1_000_000:.3f}s"
    if duration >= 1_000:
        return f"{duration / 1_000:.3f}ms"
    return f"{duration:.0f}us"


def _node_label(node_key: tuple[str, str]) -> str:
    """Format a graph node key for reports."""
    cmdb_id, operation_name = node_key
    return f"{cmdb_id}::{operation_name}"


def _latency_score(latency_value: float, latency_baseline: float) -> float:
    """Calculate capped relative latency increase against baseline."""
    if pd.isna(latency_value) or pd.isna(latency_baseline) or latency_value <= 0:
        return 0.0
    relative_increase = (float(latency_value) - float(latency_baseline)) / float(latency_value)
    return min(max(relative_increase, 0.0), 2.0)


def _build_latency_detail(latency_series: pd.Series) -> dict[str, Any]:
    """Build common latency detail fields."""
    return {
        "max_latency": float(latency_series.max()),
        "p99_latency": float(latency_series.quantile(0.99)),
        "p95_latency": float(latency_series.quantile(0.95)),
    }


def _build_baseline_latency_detail(latency_series: pd.Series) -> dict[str, Any]:
    """Build baseline latency detail fields."""
    if latency_series.empty:
        return {
            "max_latency_baseline": float("nan"),
            "p99_latency_baseline": float("nan"),
            "p95_latency_baseline": float("nan"),
        }
    return {
        "max_latency_baseline": float(latency_series.max()),
        "p99_latency_baseline": float(latency_series.quantile(0.99)),
        "p95_latency_baseline": float(latency_series.quantile(0.95)),
    }


def _format_detail(detail: dict[str, Any]) -> str:
    """Format latency detail fields."""
    return (
        f"max latency: {_format_duration_latency(detail['max_latency'])}, "
        f"P99 latency: {_format_duration_latency(detail['p99_latency'])}, "
        f"P95 latency: {_format_duration_latency(detail['p95_latency'])}, "
        f"max latency baseline: {_format_duration_latency(detail['max_latency_baseline'])}, "
        f"P99 latency baseline: {_format_duration_latency(detail['p99_latency_baseline'])}, "
        f"P95 latency baseline: {_format_duration_latency(detail['p95_latency_baseline'])}"
    )


def _calculate_anomaly_score(detail: dict[str, Any]) -> float:
    """Calculate anomaly score from latency increases over the baseline tuple."""
    return (
        _latency_score(detail["max_latency"], detail["max_latency_baseline"])
        + _latency_score(detail["p99_latency"], detail["p99_latency_baseline"])
        + _latency_score(detail["p95_latency"], detail["p95_latency_baseline"])
    )


def _is_abnormal_status_code(status_code_value: int | None) -> bool:
    """Detect abnormal status codes using the previous status-code rule."""
    return status_code_value is not None and (1 <= status_code_value <= 15 or status_code_value >= 400)


def _status_code_anomaly_detection(
    span_detail_df: pd.DataFrame,
    limit: int = 20,
) -> str:
    """Detect abnormal status codes for each span tuple and format them as text."""
    if span_detail_df.empty:
        return ""

    working_df = span_detail_df.copy()
    working_df["status_code_numeric"] = pd.to_numeric(working_df["status_code"], errors="coerce")
    if "trace_period" in working_df.columns:
        working_df = working_df[working_df["trace_period"] == "current"].copy()
    working_df = working_df.dropna(subset=["cmdb_id", "operation_name", "status_code_numeric"]).copy()

    if working_df.empty:
        return ""

    status_rows: list[tuple[int, str, str]] = []
    grouped = working_df.groupby(["cmdb_id", "operation_name"], dropna=False, sort=False)

    for (cmdb_id, operation_name), group_df in grouped:
        status_series = pd.to_numeric(group_df["status_code_numeric"], errors="coerce").dropna()
        abnormal_status_codes = sorted(
            {
                int(status_code)
                for status_code in status_series.tolist()
                if _is_abnormal_status_code(int(status_code))
            }
        )
        if not abnormal_status_codes:
            continue

        abnormal_count = int(status_series.isin(abnormal_status_codes).sum())
        total_count = int(len(status_series))
        node_key = (str(cmdb_id), str(operation_name))
        status_code_text = ",".join(str(code) for code in abnormal_status_codes)
        line = (
            f"- {_node_label(node_key)}, abnormal status_code: {status_code_text}, "
            f"abnormal ratio: {abnormal_count}/{total_count}"
        )
        status_rows.append((abnormal_count, _node_label(node_key), line))

    if not status_rows:
        return ""

    status_rows.sort(key=lambda item: (-item[0], item[1]))
    lines = ["### Status-code anomalies:"]
    lines.extend(line for _abnormal_count, _node_label_text, line in status_rows[:limit])
    return "\n".join(lines)


def _span_anomaly_detection(
    span_detail_df: pd.DataFrame,
    latency_report_threshold: int,
) -> str:
    """Build a span tuple graph, rank root causes, and format the analysis as text."""
    if span_detail_df.empty:
        return ""

    working_df = span_detail_df.copy()
    working_df["latency"] = pd.to_numeric(working_df["latency"], errors="coerce")
    working_df = working_df.dropna(subset=["cmdb_id", "operation_name", "latency"]).copy()

    if working_df.empty:
        return ""

    if "trace_period" not in working_df.columns:
        working_df["trace_period"] = "current"

    current_df = working_df[working_df["trace_period"] == "current"].copy()
    baseline_df = working_df[working_df["trace_period"] == "baseline"].copy()

    if current_df.empty:
        return ""

    graph_nodes: set[tuple[str, str]] = set()
    node_details: dict[tuple[str, str], dict[str, Any]] = {}
    baseline_details: dict[tuple[str, str], dict[str, Any]] = {}
    baseline_grouped = baseline_df.groupby(["cmdb_id", "operation_name"], dropna=False, sort=False)

    for (cmdb_id, operation_name), group_df in baseline_grouped:
        latency_series = pd.to_numeric(group_df["latency"], errors="coerce").dropna()
        node_key = (str(cmdb_id), str(operation_name))
        baseline_details[node_key] = _build_baseline_latency_detail(latency_series)

    grouped = current_df.groupby(["cmdb_id", "operation_name"], dropna=False, sort=False)

    for (cmdb_id, operation_name), group_df in grouped:
        latency_series = pd.to_numeric(group_df["latency"], errors="coerce").dropna()
        if latency_series.empty:
            continue

        node_key = (str(cmdb_id), str(operation_name))
        graph_nodes.add(node_key)
        node_details[node_key] = {
            **_build_latency_detail(latency_series),
            **baseline_details.get(node_key, _build_baseline_latency_detail(pd.Series(dtype="float64"))),
        }

    if not graph_nodes:
        return ""

    span_node_df = current_df[["trace_id", "span_id", "cmdb_id", "operation_name"]].copy()
    span_node_df["node_key"] = list(
        zip(span_node_df["cmdb_id"].astype(str), span_node_df["operation_name"].astype(str))
    )
    span_to_node = {
        (row.trace_id, row.span_id): row.node_key
        for row in span_node_df.itertuples(index=False)
    }

    edges: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for row in current_df.itertuples(index=False):
        child_node = (str(row.cmdb_id), str(row.operation_name))
        if child_node not in graph_nodes or pd.isna(row.parent_span):
            continue
        parent_node = span_to_node.get((row.trace_id, row.parent_span))
        if parent_node is None or parent_node not in graph_nodes or parent_node == child_node:
            continue
        edges.add((parent_node, child_node))

    children: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    parents: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)

    for parent_node, child_node in edges:
        children[parent_node].add(child_node)
        parents[child_node].add(parent_node)

    self_anomaly = {
        node: _calculate_anomaly_score(node_details[node])
        for node in graph_nodes
    }
    root_cause_scores: dict[tuple[str, str], float] = {}
    for node in graph_nodes:
        upstream_impact = sum(self_anomaly[parent] * 0.3 for parent in parents.get(node, set()))
        children_explanation = sum(self_anomaly[child] * 0.3 for child in children.get(node, set()))
        root_cause_scores[node] = self_anomaly[node] + upstream_impact - children_explanation

    candidate_nodes = [
        node
        for node in graph_nodes
        if self_anomaly[node] > 0 and node_details[node]["max_latency"] > latency_report_threshold
    ]
    if not candidate_nodes:
        return ""

    top_nodes = sorted(
        candidate_nodes,
        key=lambda node: (-root_cause_scores[node], -self_anomaly[node], _node_label(node)),
    )

    lines = ["### Suspicious span tuples:"]
    for rank, node in enumerate(top_nodes, start=1):
        lines.append(
            f"{rank}. {_node_label(node)}, root cause score: {root_cause_scores[node]:.3f}, "
            f"anomaly score: {self_anomaly[node]:.3f}, {_format_detail(node_details[node])}"
        )

    return "\n".join(lines)


def trace_anomalies(state: "WorkflowState") -> dict[str, Any]:
    """Build trace anomalies text and anomaly flag for routing."""
    dataset_config = get_dataset_config(state.get("dataset"))
    trace_df = _load_trace_dataframe(state["date"], state["start_timestamp"], dataset_config.name)
    span_detail_df = _build_trace_detail_dataframe(trace_df)

    if span_detail_df.empty:
        return {
            "trace_anomalies": "No span anomalies found.",
            "is_trace_anomaly": "False",
        }

    anomaly_sections = [
        section
        for section in (
            _span_anomaly_detection(span_detail_df, dataset_config.latency_report_threshold),
            _status_code_anomaly_detection(span_detail_df),
        )
        if section
    ]
    span_anomalies = "\n\n".join(anomaly_sections)

    if not span_anomalies:
        return {
            "trace_anomalies": "No span anomalies found.",
            "is_trace_anomaly": "False",
        }
    return {
        "trace_anomalies": span_anomalies,
        "is_trace_anomaly": "True",
    }
