"""Shared exception types for layer-neutral error signalling.

The tools layer must never import from the assistant layer; protocol errors
raised at the tool boundary live here and are re-exported by
assistant.task_contract for compatibility.
"""


class TaskProtocolError(ValueError):
    def __init__(self,code,message,*,field_path=None,validation=None,step_id=None):
        self.code=code
        if field_path is not None:self.field_path=list(field_path)
        if validation is not None:self.validation=validation
        if step_id is not None:self.step_id=step_id
        super().__init__(message)


def _union_branch(error):
    """Index of the union branch that produced this child error.

    ``schema_path`` begins with the keyword itself ('oneOf'), so the branch
    index is only available in ``absolute_schema_path``. The innermost union
    is the one this child belongs to.
    """
    path=list(error.absolute_schema_path);index=None
    for position,part in enumerate(path):
        if part in ('oneOf','anyOf') and position+1<len(path) and type(path[position+1]) is int:
            index=path[position+1]
    return index


def _outermost_union(error):
    """Highest union on the ancestor chain.

    jsonschema.validate reports a leaf chosen by best_match, so the union that
    actually rejected the input is only reachable through ``parent``. Judging
    the outermost union first keeps the operation branch authoritative.
    """
    node=error;found=None
    while node is not None:
        if node.validator in ('oneOf','anyOf'):found=node
        node=node.parent
    return found


def _inner_union(error,stop):
    """Innermost union strictly between the selected error and the union above it."""
    node=error.parent
    while node is not None and node is not stop:
        if node.validator in ('oneOf','anyOf'):return node
        node=node.parent
    return None


def _branch_children(union):
    """Children of the branch whose explicit discriminator matches the instance."""
    groups={}
    for child in union.context:
        index=_union_branch(child)
        if index is not None:groups.setdefault(index,[]).append(child)
    if not groups:return None
    branches=union.schema.get(union.validator,[])
    def score(pair):
        index,children=pair
        schema=branches[index] if 0<=index<len(branches) else {}
        matches=mismatches=0
        if isinstance(union.instance,dict):
            for name,rule in schema.get('properties',{}).items():
                if name not in union.instance:continue
                if 'const' in rule or 'enum' in rule:
                    accepted=union.instance[name] in rule.get('enum',[rule.get('const')])
                    matches+=int(accepted);mismatches+=int(not accepted)
        return mismatches,-matches,len(children)
    return min(groups.items(),key=score)[1]


def schema_protocol_error(error,code,message,*,prefix=()):
    """Select the failed union branch without echoing input values or schema dumps."""
    from jsonschema.exceptions import best_match
    issue=error if error.validator in ('oneOf','anyOf') else (_outermost_union(error) or error)
    # Union errors frequently contain several nested failures. Select the
    # branch matching explicit discriminators (operation/type), rather than
    # best_match's deliberately conservative parent oneOf error.
    while issue.validator in ('oneOf','anyOf') and issue.context:
        children=_branch_children(issue)
        if not children:break
        selected=best_match(children)
        deeper=selected if selected.validator in ('oneOf','anyOf') else _inner_union(selected,issue)
        if deeper is None:
            issue=selected;break
        issue=deeper
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
