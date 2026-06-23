from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config.llm_config import get_openai_lm

from ..utils import get_dataset_prompt, parse_structured_json_response

if TYPE_CHECKING:
    from ..workflow import WorkflowState


class LogAgentResult(BaseModel):
    """Structured output schema for log analysis."""

    log_summary: str = Field(description="Plain-text summary of overall log behavior during the fault window.")
    suspicious_components_from_log: list[str] = Field(
        description="A list of suspicious node, pod, or service names recommended for metric checking."
    )


def log_agent(state: "WorkflowState") -> dict[str, Any]:
    """Run the log LLM node and return structured log analysis."""
    log_anomalies = str(state.get("log_anomalies", "")).strip()
    log_normal = str(state.get("log_normal", "")).strip()
    if not log_anomalies or log_anomalies == "No log anomalies found.":
        return {
            "log_summary": "No meaningful log anomalies found within the fault window.",
            "suspicious_components_from_log": [],
        }

    llm = get_openai_lm().with_structured_output(
        LogAgentResult,
        method="json_mode",
        include_raw=True,
    )
    response = llm.invoke(
        [
            SystemMessage(content=get_dataset_prompt(state.get("dataset"), "LOG_AGENT_SYSTEM_PROMPT")),
            HumanMessage(
                content=(
                    f"{get_dataset_prompt(state.get('dataset'), 'LOG_AGENT_USER_PROMPT').strip()}\n"
                    f"{get_dataset_prompt(state.get('dataset'), 'MICROSERVICE_SYSTEM_PROMPT').strip()}\n"
                    f"# Normal Log Patterns\n{log_normal or 'No normal log patterns found.'}\n\n"
                    f"# Fault-window Log Patterns\n{log_anomalies}"
                )
            ),
        ]
    )
    parsed_result = parse_structured_json_response(response)
    suspicious_components = parsed_result.get("suspicious_components_from_log", [])
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
        "log_summary": str(parsed_result.get("log_summary", "")).strip(),
        "suspicious_components_from_log": normalized_components,
    }
