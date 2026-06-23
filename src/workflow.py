import operator
from typing import Annotated, Any

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from .nodes.log_agent import log_agent
from .nodes.log_anomalies import log_anomalies
from .nodes.metric_agent import metric_agent
from .nodes.metric_anomalies import metric_anomalies
from .nodes.rca_expert import rca_expert
from .nodes.trace_agent import trace_agent
from .nodes.trace_anomalies import trace_anomalies
from .tools import add, delete


class WorkflowState(TypedDict, total=False):
    """State for the LangGraph workflow."""

    dataset: str
    date: str
    start_timestamp: str
    log_anomalies: str
    log_normal: str
    log_summary: str
    suspicious_components_from_log: list[str]
    metric_anomalies: list[dict[str, Any]]
    metric_summary: str
    filtered_metric_anomalies: list[dict[str, Any]]
    deleted_metric_anomalies: list[dict[str, Any]]
    metric_agent_message: Annotated[list[AnyMessage], operator.add]
    metric_agent_queries_times: int
    trace_anomalies: str
    is_trace_anomaly: str
    trace_summary: str
    suspicious_components_from_trace: list[str]
    rca_result: dict[str, Any]


def _route_from_metric_agent(state: WorkflowState) -> str:
    """Route metric agent output either to tools or RCA."""
    metric_agent_message = list(state.get("metric_agent_message", []))
    if not metric_agent_message:
        return "rca_expert"

    last_message = metric_agent_message[-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "metric_tool"
    return "rca_expert"


def build_workflow():
    """Construct and compile the LangGraph RCA workflow."""
    graph = StateGraph(WorkflowState)

    graph.add_node("metric_anomalies", metric_anomalies)
    graph.add_node("log_anomalies", log_anomalies)
    graph.add_node("log_agent", log_agent)
    graph.add_node("trace_anomalies", trace_anomalies)
    graph.add_node("trace_agent", trace_agent)
    graph.add_node("metric_agent", metric_agent)
    graph.add_node("metric_tool", ToolNode([add, delete], messages_key="metric_agent_message"))
    graph.add_node("rca_expert", rca_expert)

    graph.add_edge(START, "metric_anomalies")
    graph.add_edge(START, "log_anomalies")
    graph.add_edge(START, "trace_anomalies")
    graph.add_edge("log_anomalies", "log_agent")
    graph.add_edge("trace_anomalies", "trace_agent")
    graph.add_edge(["metric_anomalies", "log_agent", "trace_agent"], "metric_agent")
    graph.add_conditional_edges(
        "metric_agent",
        _route_from_metric_agent,
        {
            "metric_tool": "metric_tool",
            "rca_expert": "rca_expert",
        },
    )
    graph.add_edge("metric_tool", "metric_agent")
    graph.add_edge("rca_expert", END)

    return graph.compile()
