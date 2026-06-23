from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config.llm_config import get_openai_lm

from ..utils import get_dataset_prompt, parse_structured_json_response

if TYPE_CHECKING:
    from ..workflow import WorkflowState


class RootCauseItem(BaseModel):
    """Structured schema for a single root-cause candidate."""

    location: str = Field(description="A node, pod, or service name from the provided context.")
    reason: str = Field(description="Plain-text evidence-based explanation within 500 words.")


class RCAResult(BaseModel):
    """Structured output schema for RCA results."""

    root_causes: list[RootCauseItem] = Field(description="Exactly 5 root causes in descending order of likelihood.")


def rca_expert(state: "WorkflowState") -> dict[str, Any]:
    """Run RCA once and directly return the ranked root causes."""
    metric_summary = str(state.get("metric_summary", "")).strip()
    log_summary = str(state.get("log_summary", "")).strip()
    trace_summary = str(state.get("trace_summary", "")).strip()

    llm = get_openai_lm().with_structured_output(
        RCAResult,
        method="json_mode",
        include_raw=True,
    )
    response = llm.invoke(
        [
            SystemMessage(content=get_dataset_prompt(state.get("dataset"), "RCA_EXPERT_SYSTEM_PROMPT")),
            HumanMessage(
                content=(
                    f"{get_dataset_prompt(state.get('dataset'), 'RCA_EXPERT_USER_PROMPT').strip()}\n\n"
                    f"{get_dataset_prompt(state.get('dataset'), 'MICROSERVICE_SYSTEM_PROMPT').strip()}\n"
                    f"## Log Summary\n{log_summary}\n"
                    f"## Metric Summary\n{metric_summary}\n"
                    f"## Trace Summary\n{trace_summary}"
                ).strip()
            ),
        ]
    )
    parsed_result = parse_structured_json_response(response)
    root_causes = parsed_result.get("root_causes", [])
    if isinstance(root_causes, list) and len(root_causes) == 5:
        return {"rca_result": {"root_causes": root_causes}}
    return {"rca_result": parsed_result}
