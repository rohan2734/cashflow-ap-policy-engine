from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class RawBlock:
    text: str
    page: int

@dataclass(frozen=True)
class Clause:
    id: str
    text: str
    page: int

@dataclass(frozen=True)
class EnrichedClause:
    id: str
    text: str
    page: int
    referenced_texts: list[str]

@dataclass(frozen=True)
class RawExtraction:
    clause_id: str
    condition_raw: dict[str, Any]
    action_raw: str
    exceptions_raw: list[str]

@dataclass(frozen=True)
class ValidatedExtraction:
    clause_id: str
    condition: dict[str, Any]
    action: str
    exceptions: list[str]
    confidence: float