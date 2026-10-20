"""Compatibility entry point for the native Python workflow."""
from graph_research.workflow import build_workflow, validate_task, verify_result, main
from graph_research.backend import NativeBackend

if __name__ == "__main__":
    raise SystemExit(main())
