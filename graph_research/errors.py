"""Shared exception types for layer-neutral error signalling.

The tools layer must never import from the assistant layer; protocol errors
raised at the tool boundary live here and are re-exported by
assistant.task_contract for compatibility.
"""


class TaskProtocolError(ValueError):
    def __init__(self,code,message):self.code=code;super().__init__(message)


class FieldValidationError(ValueError):
    """Safe input correction metadata; deliberately excludes the input value."""
    code='invalid_field'

    def __init__(self,path,expected,message):
        self.field_path=list(path)
        self.validation={key:expected[key] for key in ('type','enum','minimum','maximum','pattern','minItems','maxItems','maxLength') if key in expected}
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
