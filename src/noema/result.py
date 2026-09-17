from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Check:
    rule_id: str
    severity: str
    result: str
    message: str
    path: str | None = None
    fix_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Report:
    status: str
    project_id: str | None
    checks: list[Check]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_id": self.project_id,
            "checks": [c.to_dict() for c in self.checks],
        }

    @property
    def has_errors(self) -> bool:
        return any(c.severity == "ERROR" and c.result == "FAIL" for c in self.checks)
