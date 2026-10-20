"""Compatible agent entry point; governed workflow is in feature_agent."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("graph_research.assistant.feature_agent")
