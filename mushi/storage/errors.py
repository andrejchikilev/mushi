"""Storage-specific exceptions."""


class StorageError(Exception):
    """Base class for storage failures."""


class RecordNotFoundError(StorageError):
    """Raised when a requested record file does not exist."""


class InvalidRecordError(StorageError):
    """Raised when stored data cannot be decoded or validated."""


class RecordAlreadyExistsError(StorageError):
    """Raised when append-only storage would overwrite an existing record."""
