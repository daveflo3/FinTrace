from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NodeKind(StrEnum):
    EVIDENCE = "evidence"
    ASSUMPTION = "assumption"
    CALCULATION = "calculation"
    OUTPUT = "output"
    JUDGEMENT = "judgement"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Node(BaseModel):
    """A single object in a financial reasoning chain."""

    id: str = Field(min_length=1)
    kind: NodeKind
    label: str = Field(min_length=1)
    description: str | None = None

    value: Any | None = None
    unit: str | None = None

    rationale: str | None = None
    confidence: Confidence | None = None

    source_uri: str | None = None
    source_quote: str | None = None
    as_of: datetime | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
