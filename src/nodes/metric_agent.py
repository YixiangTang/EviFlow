import json
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from config.llm_config import get_openai_lm
from ..datasets import get_dataset_config
from ..tools import add, delete
from ..utils import get_dataset_prompt

if TYPE_CHECKING:
    from ..workflow import WorkflowState


def _add_service_suffix(components: Any, dataset: str | None) -> list[str]:
    """Expand non-numeric component names into grpc/http protocol variants."""
    if not isinstance(components, list):
        return []
    dataset_config = get_dataset_config(dataset)

    expanded_components: list[str] = []
    for item in components:
        component = str(item).strip()
        if not component:
            continue
        if not dataset_config.expand_service_protocol_suffixes or component[-1].isdigit():
            expanded_components.append(component)
            continue
        expanded_components.append(f"{component}-grpc")
        expanded_components.append(f"{component}-http")
    return expanded_components


def _list_to_prompt(metric_items: Any, dataset: str | None) -> str:
    """Format metric anomaly items into readable prompt text."""
    if not isinstance(metric_items, list) or not metric_items:
        return "## Metric Anomalies\nNo metric anomalies."

    metric_descriptions = get_dataset_config(dataset).metric_descriptions
    lines: list[str] = []
    used_metrics: list[str] = []
    seen_metrics: set[str] = set()
    for item in metric_items:
        if not isinstance(item, dict):
            continue
        component = str(item.get("component", "")).strip()
        metric = str(item.get("metric", "")).strip()
        score = float(item.get("score", 0.0))
        values_text = str(item.get("values_text", "")).strip()
        mad_threshold = str(item.get("mad_threshold", "")).strip()
        if not component or not metric:
            continue
        lines.append(
            f"- component: {component}, metric: {metric}, anomaly score(0-1): {score:.2f}, "
            f"values: {values_text}, mad_threshold: {mad_threshold}"
        )
        if metric not in seen_metrics:
            seen_metrics.add(metric)
            used_metrics.append(metric)

    if not lines:
        return "## Metric Anomalies\nNo metric anomalies."

    description_lines = ["### Metric Description"]
    for metric in used_metrics:
        description = metric_descriptions.get(metric, "")
        description_lines.append(f"- {metric}: {description}")

    return "\n".join(["## Metric Anomalies", *lines, "", *description_lines])


def metric_agent(state: "WorkflowState") -> dict[str, Any]:
    """Run one metric-agent turn and keep conversation state."""

    metric_agent_message = list(state.get("metric_agent_message", []))
    metric_agent_queries_times = int(state.get("metric_agent_queries_times", 0))
    dataset = state.get("dataset")
    dataset_config = get_dataset_config(dataset)

    filtered_metric_anomalies = state.get("filtered_metric_anomalies", [])
    deleted_metric_anomalies = state.get("deleted_metric_anomalies", [])
    trace_summary = str(state.get("trace_summary", "")).strip()
    log_summary = str(state.get("log_summary", "")).strip()
    metric_anomalies = state.get("metric_anomalies", [])

    if metric_agent_message and isinstance(metric_agent_message[-1], ToolMessage):
        try:
            tool_payload = json.loads(str(metric_agent_message[-1].content))
        except json.JSONDecodeError:
            tool_payload = {}
        filtered_metric_anomalies = tool_payload.get("filtered_metric_anomalies", [])
        deleted_metric_anomalies = tool_payload.get("deleted_metric_anomalies", [])

    else:
        if not metric_anomalies:
            return {
                "filtered_metric_anomalies": [],
                "deleted_metric_anomalies": deleted_metric_anomalies,
                "metric_agent_message": [],
                "metric_agent_queries_times": metric_agent_queries_times,
                "metric_summary": "No meaningful metric anomalies found within the fault window.",
            }
        suspicious_components_from_trace = _add_service_suffix(
            state.get("suspicious_components_from_trace", []),
            dataset,
        )
        suspicious_components_from_log = _add_service_suffix(
            state.get("suspicious_components_from_log", []),
            dataset,
        )
        filtered_metric_anomalies = []
        for index, item in enumerate(metric_anomalies):
            if not isinstance(item, dict):
                continue
            component = str(item.get("component", "")).strip()
            if index < dataset_config.filter_list_init_num:
                filtered_metric_anomalies.append(item)
            elif component in suspicious_components_from_trace:
                filtered_metric_anomalies.append(item)
            elif component in suspicious_components_from_log:
                filtered_metric_anomalies.append(item)

    all_metric_anomalies_accounted = (
        len(filtered_metric_anomalies) + len(deleted_metric_anomalies) == len(metric_anomalies)
    )

    if all_metric_anomalies_accounted:
        tool_usage_prompt = """
## Action Selection
- In this round, you must choose exactly one action: `delete`, or `summary`.
- Use `delete` when one metric anomaly is useless for further analysis.
- Before using `delete`, evaluate each component-metric pair together with related anomalies, including other metrics on the same component and service-pod relationships.
- Preserve a weak anomaly if its related component-metric pairs show clear anomalies and it can still provide useful supporting evidence.
- You may still use `delete` for anomalies that remain extremely weak or marginal after considering these relationships.
- If the Metric Anomalies is already adequate for downstream diagnosis, do not use tools but return a summary.

## Tool Calling Rules
- If you choose `delete`, use tool calling only.
- Do not choose `delete` when the items in Metric Anomalies is already very limited (e.g., less than 3).
- You may make multiple tool calls, but they must all use the same tool name.

## Summary Requirements
- If you choose `summary`, return a plain-text summary of the Metric Anomalies.
- Do not perform any root cause analysis.
- Do not give any recovery suggestions.
- No need to consider trace and log summaries when writing the summary.
- The summary should directly summarize the Metric Anomalies and be suitable for downstream RCA use.
- Keep the summary under 1000 words.
"""
    elif metric_agent_queries_times >= dataset_config.force_summary_rounds:
        tool_usage_prompt = """
## Action Selection
- In this round, you must return a summary and not call any tools.

## Summary Requirements
- The summary should directly summarize the Metric Anomalies and be suitable for downstream RCA use.
- Do not perform any root cause analysis.
- Do not give any recovery suggestions.
- No need to consider trace and log summaries when writing the summary.
- Keep the summary under 1000 words.
"""
    elif metric_agent_queries_times < dataset_config.force_tool_calling_rounds:
        tool_usage_prompt = """
## Action Selection
- In this round, you must use tool calling.
- Choose exactly one tool name: `add` or `delete`.
- Use `add` when you want more metric evidence.
- Use `add` when the component types in Metric Anomalies is less than 5.
- Use `delete` when one metric anomaly is useless for further analysis.
- Before using `delete`, evaluate each component-metric pair together with related anomalies, including other metrics on the same component and service-pod relationships.
- Preserve a weak anomaly if its related component-metric pairs show clear anomalies and it can still provide useful supporting evidence.
- You may still use `delete` for anomalies that remain extremely weak or marginal after considering these relationships.

## Tool Calling Rules
- You may make multiple tool calls, but they must all use the same tool name.
- Do not choose `delete` when the items in Metric Anomalies is already very limited (e.g., less than 3).
- Do not return a summary in this round.
""".strip()
    else:
        tool_usage_prompt = """
## Action Selection
- In this round, you must choose exactly one action: `add`, `delete`, or `summary`.
- Use `add` when you want more metric evidence.
- Use `add` when the component types in Metric Anomalies is less than 5.
- Use `delete` when one metric anomaly is useless for further analysis.
- Before using `delete`, evaluate each component-metric pair together with related anomalies, including other metrics on the same component and service-pod relationships.
- Preserve a weak anomaly if its related component-metric pairs show clear anomalies and it can still provide useful supporting evidence.
- You may still use `delete` for anomalies that remain extremely weak or marginal after considering these relationships.
- If the Metric Anomalies is already adequate for downstream diagnosis, do not use tools but return a summary.

## Tool Calling Rules
- If you choose `add` or `delete`, use tool calling only.
- Do not choose `delete` when the items in Metric Anomalies is already very limited (e.g., less than 3).
- You may make multiple tool calls, but they must all use the same tool name.

## Summary Requirements
- If you choose `summary`, return a plain-text summary of the Metric Anomalies.
- Do not perform any root cause analysis.
- Do not give any recovery suggestions.
- No need to consider trace and log summaries when writing the summary.
- The summary should directly summarize the Metric Anomalies and be suitable for downstream RCA use.
- Keep the summary under 1000 words.
""".strip()

    llm = get_openai_lm().bind_tools([add, delete])
    filtered_metric_anomalies_text = _list_to_prompt(filtered_metric_anomalies, dataset)
    response = llm.invoke(
        [
            SystemMessage(content=get_dataset_prompt(dataset, "METRIC_AGENT_SYSTEM_PROMPT")),
            HumanMessage(
                content=(
                    f"{get_dataset_prompt(dataset, 'METRIC_AGENT_USER_PROMPT').format(tool_usage_prompt=tool_usage_prompt).strip()}\n"
                    f"{get_dataset_prompt(dataset, 'MICROSERVICE_SYSTEM_PROMPT').strip()}\n"
                    f"## Trace Summary\n{trace_summary}"
                    f"## Log Summary\n{log_summary}\n"
                    f"{filtered_metric_anomalies_text}"
                )
            ),
        ]
    )

    result = {
        "filtered_metric_anomalies": filtered_metric_anomalies,
        "deleted_metric_anomalies": deleted_metric_anomalies,
        "metric_agent_message": [response],
        "metric_agent_queries_times": metric_agent_queries_times + 1,
    }
    if isinstance(response, AIMessage) and not getattr(response, "tool_calls", None):
        content = getattr(response, "content", "")
        result["metric_summary"] = content.strip() if isinstance(content, str) else str(content).strip()

    return result
