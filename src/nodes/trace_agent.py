from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config.llm_config import get_openai_lm

from ..utils import get_dataset_prompt, parse_structured_json_response


if TYPE_CHECKING:
    from ..workflow import WorkflowState


class TraceAgentResult(BaseModel):
    """Structured output schema for trace analysis."""

    trace_summary: str = Field(description="Plain-text summary of overall trace behavior during the fault window.")
    suspicious_components_from_trace: list[str] = Field(
        description="A list of suspicious node, pod, or service names recommended for metric checking."
    )


def trace_agent(state: "WorkflowState") -> dict[str, Any]:
    """Run the trace LLM node and return structured trace analysis."""
    is_trace_anomaly = state.get("is_trace_anomaly", "False")
    if is_trace_anomaly == "False":
        return {
            "trace_summary": "No meaningful trace anomalies found within the fault window.",
            "suspicious_components_from_trace": [],
        }

    llm = get_openai_lm().with_structured_output(
        TraceAgentResult,
        method="json_mode",
        include_raw=True,
    )
    invocation_messages = [
        SystemMessage(content=get_dataset_prompt(state.get("dataset"), "TRACE_AGENT_SYSTEM_PROMPT")),
        HumanMessage(
            content=(
                f"{get_dataset_prompt(state.get('dataset'), 'TRACE_AGENT_USER_PROMPT').strip()}\n"
                f"{get_dataset_prompt(state.get('dataset'), 'MICROSERVICE_SYSTEM_PROMPT').strip()}\n"
                f"#Trace Anomalies\n{state.get('trace_anomalies', '')}"
            )
        ),
    ]

    response = llm.invoke(invocation_messages)
    parsed_result = parse_structured_json_response(response)
    suspicious_components = parsed_result.get("suspicious_components_from_trace", [])
    if not isinstance(suspicious_components, list):
        suspicious_components = []

    normalized_components: list[str] = []
    seen_components: set[str] = set()
    for item in suspicious_components:
        component = str(item).strip()
        if component and component not in seen_components:
            seen_components.add(component)
            normalized_components.append(component)

    return {
        "trace_summary": str(parsed_result.get("trace_summary", "")).strip(),
        "suspicious_components_from_trace": normalized_components,
    }
