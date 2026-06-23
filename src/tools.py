import json
import random
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from .datasets import get_dataset_config


def _metric_key(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("component", "")).strip(),
        str(item.get("metric", "")).strip(),
    )


@tool
def add(
    original_sequence: Annotated[Any | None, InjectedState("metric_anomalies")],
    current_sequence: Annotated[Any | None, InjectedState("filtered_metric_anomalies")],
    deleted_sequence: Annotated[Any | None, InjectedState("deleted_metric_anomalies")],
) -> str:
    """Add one random metric anomaly that is already detected and has not been analyzed."""
    deleted_items = deleted_sequence if isinstance(deleted_sequence, list) else []
    if not isinstance(original_sequence, list):
        updated_sequence = []
    else:
        current_items = current_sequence if isinstance(current_sequence, list) else []
        existing_keys = {
            _metric_key(item)
            for item in current_items
            if isinstance(item, dict)
        }
        deleted_keys = {
            _metric_key(item)
            for item in deleted_items
            if isinstance(item, dict)
        }
        candidates = [
            item for item in original_sequence
            if isinstance(item, dict)
            and _metric_key(item) not in existing_keys
            and _metric_key(item) not in deleted_keys
        ]
        updated_sequence = list(current_items)
        if candidates:
            updated_sequence.append(random.choice(candidates))

    return json.dumps(
        {
            "filtered_metric_anomalies": updated_sequence,
            "deleted_metric_anomalies": deleted_items,
        },
        ensure_ascii=True,
    )


@tool
def delete(
    component: str,
    metric: str,
    current_sequence: Annotated[Any | None, InjectedState("filtered_metric_anomalies")],
    deleted_sequence: Annotated[Any | None, InjectedState("deleted_metric_anomalies")],
    dataset: Annotated[str | None, InjectedState("dataset")],
) -> str:
    """Delete one metric anomaly identified by the (component, metric) pair."""
    if not isinstance(current_sequence, list):
        updated_sequence = []
        deleted_metric_anomalies = deleted_sequence if isinstance(deleted_sequence, list) else []
    else:
        normalized_component = str(component).strip()
        normalized_metric = str(metric).strip()
        dataset_config = get_dataset_config(dataset)
        if (
            dataset_config.expand_service_protocol_suffixes
            and normalized_component
            and not normalized_component[-1].isdigit()
            and not normalized_component.endswith("-grpc")
            and not normalized_component.endswith("-http")
        ):
            candidate_components = {
                f"{normalized_component}-grpc",
                f"{normalized_component}-http",
            }
        else:
            candidate_components = {normalized_component}
        deleted_metric_anomalies = list(deleted_sequence) if isinstance(deleted_sequence, list) else []
        updated_sequence = [
            item for item in current_sequence
            if not (
                isinstance(item, dict)
                and str(item.get("component", "")).strip() in candidate_components
                and str(item.get("metric", "")).strip() == normalized_metric
            )
        ]
        deleted_items = [
            item for item in current_sequence
            if (
                isinstance(item, dict)
                and str(item.get("component", "")).strip() in candidate_components
                and str(item.get("metric", "")).strip() == normalized_metric
            )
        ]
        deleted_metric_anomalies.extend(deleted_items)

    return json.dumps(
        {
            "filtered_metric_anomalies": updated_sequence,
            "deleted_metric_anomalies": deleted_metric_anomalies,
        },
        ensure_ascii=True,
    )
