"""Core workflow exceptions."""


class WorkflowError(Exception):
    """Base class for workflow-level failures."""


class RecordConflictError(WorkflowError):
    """Raised when a workflow would overwrite an existing logical record."""


class InvalidWorkflowStateError(WorkflowError):
    """Raised when a workflow transition is not valid."""
