"""Optional model selection and experimental tool generation."""
from importlib import import_module
_EXPORTS = {'build_agent':('agent','build_agent'),'ConfiguredModel':('model','ConfiguredModel'),
            'ToolStore':('graph_research.tools.extensions','ToolStore'),'ResearchSession':('session','ResearchSession'),
            'UserMemoryStore':('memory','UserMemoryStore'),'verify_bundle':('results','verify_bundle'),
            'OfflineToolSession':('offline','OfflineToolSession'),
            'ModelSettings':('model_config','ModelSettings'),'configuration_status':('model_config','configuration_status'),
            'create_subagent':('subagent','create_subagent'),'SubagentLimits':('task_control','SubagentLimits'),
            'subagent_contracts':('task_contract','contracts'),'subagent_tool_definition':('task_contract','tool_definition')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS: raise AttributeError(name)
    module,attribute = _EXPORTS[name]
    value = getattr(import_module(module if module.startswith('graph_research.') else __name__+'.'+module),attribute)
    globals()[name] = value
    return value
