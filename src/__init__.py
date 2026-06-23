def build_workflow():
    from .workflow import build_workflow as _build_workflow

    return _build_workflow()

__all__ = ["build_workflow"]
