"""Shared exception types for layer-neutral error signalling.

The tools layer must never import from the assistant layer; protocol errors
raised at the tool boundary live here and are re-exported by
assistant.task_contract for compatibility.
"""


class TaskProtocolError(ValueError):
    def __init__(self,code,message,*,field_path=None,validation=None):
        self.code=code
        if field_path is not None:self.field_path=list(field_path)
        if validation is not None:self.validation=validation
        super().__init__(message)


def schema_protocol_error(error,code,message,*,prefix=()):
    """Select the failed union branch without echoing input values or schema dumps."""
    from jsonschema.exceptions import best_match
    issue=best_match([error])
    path=[*prefix,*issue.absolute_path]
    # Required property names come from our schema, never from an unknown key.
    if issue.validator=='required' and isinstance(issue.instance,dict):
        missing=[name for name in issue.validator_value if name not in issue.instance]
        if missing:path.append(missing[0])
    path=[part if type(part) is int else part[:128] for part in path[:32]]
    hints={'type':'字段类型不正确。','required':'缺少必填字段。','additionalProperties':'包含不支持的字段。',
           'minimum':'数值低于允许下限。','maximum':'数值超过允许上限。','enum':'请选择约定的选项。',
           'const':'字段值与当前操作不符。','minItems':'列表元素数量不足。','maxItems':'列表元素数量超限。',
           'uniqueItems':'列表中存在重复项。','pattern':'字段格式不符合约定。'}
    hint=hints.get(issue.validator,'字段不符合协议。')
    location='.'.join(map(str,path)) or '$'
    return TaskProtocolError(code,message+' '+location+'：'+hint,field_path=path,
                             validation={issue.validator:issue.validator_value})


class FieldValidationError(ValueError):
    """Safe input correction metadata; deliberately excludes the input value."""
    code='invalid_field'

    def __init__(self,path,expected,message):
        self.field_path=list(path)
        self.validation={key:expected[key] for key in ('type','enum','minimum','maximum','pattern','minItems','maxItems','maxLength','uniqueItems') if key in expected}
        super().__init__('.'.join(map(str,path))+': '+message)


class PathBoundaryError(PermissionError):
    """A write would cross the task/core boundary or use a device/link alias."""
    code='sandbox_violation'


class PathLengthError(OSError):
    """The filesystem cannot represent this path; repeating it cannot help."""
    code='path_too_long'


class SessionBusyError(RuntimeError):
    """A known host lock is held; do not mistake arbitrary runtime errors for it."""
    code='host_busy'
