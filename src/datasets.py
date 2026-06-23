from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.components import nodes as aiops_nodes
from config.components import pods as aiops_pods
from config.components import services as aiops_services
from config.metrics import (
    nezha_metric_descriptions,
    node_metrics,
    pod_metrics,
    rcaeval_metric_descriptions,
    service_metrics,
)
from .prompt import (
    AIOPS2022_MICROSERVICE_SYSTEM_PROMPT,
    NEZHA_MICROSERVICE_SYSTEM_PROMPT,
    RCAEVAL_MICROSERVICE_SYSTEM_PROMPT,
)


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    processed_root: Path
    microservice_system_prompt: str
    grouped_metric_layers: tuple[str, ...]
    metric_components: dict[str, list[str]]
    metric_descriptions: dict[str, str]
    expand_service_protocol_suffixes: bool
    normal_window_steps: int
    fault_window_steps: int
    min_output_score: float
    force_tool_calling_rounds: int
    force_summary_rounds: int
    latency_report_threshold: int
    filter_list_init_num: int


DATASET_CONFIGS = {
    "aiops2022": DatasetConfig(
        name="aiops2022",
        processed_root=Path("processed_data") / "aiops2022",
        microservice_system_prompt=AIOPS2022_MICROSERVICE_SYSTEM_PROMPT,
        grouped_metric_layers=("node", "pod", "service"),
        metric_components={
            "node": aiops_nodes,
            "pod": aiops_pods,
            "service": aiops_services,
        },
        metric_descriptions={**node_metrics, **pod_metrics, **service_metrics},
        expand_service_protocol_suffixes=True,
        normal_window_steps=10,
        fault_window_steps=5,
        min_output_score=0.2,
        force_tool_calling_rounds=10,
        force_summary_rounds=20,
        latency_report_threshold=800_000,
        filter_list_init_num=10,
    ),
    "nezha": DatasetConfig(
        name="nezha",
        processed_root=Path("processed_data") / "nezha",
        microservice_system_prompt=RCAEVAL_MICROSERVICE_SYSTEM_PROMPT,
        grouped_metric_layers=("service",),
        metric_components={"service": []},
        metric_descriptions=nezha_metric_descriptions,
        expand_service_protocol_suffixes=False,
        normal_window_steps=10,
        fault_window_steps=3,
        min_output_score=0.2,
        force_tool_calling_rounds=10,
        force_summary_rounds=20,
        latency_report_threshold=500_000,
        filter_list_init_num=5,
    ),
    "RCAEval": DatasetConfig(
        name="RCAEval",
        processed_root=Path("processed_data") / "RCAEval",
        microservice_system_prompt=RCAEVAL_MICROSERVICE_SYSTEM_PROMPT,
        grouped_metric_layers=("service",),
        metric_components={"service": []},
        metric_descriptions=rcaeval_metric_descriptions,
        expand_service_protocol_suffixes=False,
        normal_window_steps=10,
        fault_window_steps=5,
        min_output_score=0.2,
        force_tool_calling_rounds=10,
        force_summary_rounds=20,
        latency_report_threshold=500_000,
        filter_list_init_num=5,
    )
}


def get_dataset_config(dataset: str | None) -> DatasetConfig:
    dataset_name = (dataset or "aiops2022").strip()
    try:
        return DATASET_CONFIGS[dataset_name]
    except KeyError as exc:
        supported = ", ".join(sorted(DATASET_CONFIGS))
        raise ValueError(f"Unsupported dataset: {dataset_name}. Supported datasets: {supported}") from exc
