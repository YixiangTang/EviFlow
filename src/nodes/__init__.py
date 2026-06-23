__all__ = [
    "log_agent",
    "log_anomalies",
    "metric_agent",
    "metric_anomalies",
    "rca_expert",
    "trace_agent",
    "trace_anomalies",
]


def __getattr__(name: str):
    if name == "log_agent":
        from .log_agent import log_agent

        return log_agent
    if name == "log_anomalies":
        from .log_anomalies import log_anomalies

        return log_anomalies
    if name == "metric_agent":
        from .metric_agent import metric_agent

        return metric_agent
    if name == "metric_anomalies":
        from .metric_anomalies import metric_anomalies

        return metric_anomalies
    if name == "rca_expert":
        from .rca_expert import rca_expert

        return rca_expert
    if name == "trace_agent":
        from .trace_agent import trace_agent

        return trace_agent
    if name == "trace_anomalies":
        from .trace_anomalies import trace_anomalies

        return trace_anomalies
    raise AttributeError(name)
