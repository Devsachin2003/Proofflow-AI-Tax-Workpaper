"""Draft findings produced by pure validation rules. Persistence lives in services.findings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


def fingerprint(rule_id: str, *parts: object) -> str:
    raw = "|".join([rule_id, *[str(p) for p in parts]])
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class FindingDraft:
    rule_id: str
    fingerprint: str
    title: str
    description: str
    category: str  # confirmed_error | suspected_discrepancy | needs_judgment | informational
    severity: str  # error | warning | info
    recommended_action: str
    evidence: list[str] = field(default_factory=list)
    line_keys: list[str] = field(default_factory=list)
    affected_amount: float | None = None
    tax_category: str | None = None
    tax_delta: float | None = None
    area_id: str | None = None
    blocks_filing: bool = False
    confidence: str = "deterministic"
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return "F-" + self.fingerprint[:10]
