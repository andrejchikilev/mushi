"""JSON serialization boundary for persisted records."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from mushi.storage.errors import InvalidRecordError

RecordT = TypeVar("RecordT", bound=BaseModel)


def record_to_json(record: BaseModel) -> str:
    """Serialize a Pydantic record to stable, filesystem-safe JSON."""
    return record.model_dump_json(indent=2) + "\n"


def record_from_json(record_type: type[RecordT], raw_json: str) -> RecordT:
    """Deserialize and validate a Pydantic record from JSON text."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise InvalidRecordError(f"Invalid JSON for {record_type.__name__}") from error

    try:
        return record_type.model_validate(data)
    except ValidationError as error:
        raise InvalidRecordError(f"Invalid {record_type.__name__} record") from error
