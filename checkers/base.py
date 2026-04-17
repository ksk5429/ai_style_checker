"""Base checker interface — all checkers implement this protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Severity(Enum):
    """Issue severity level."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Issue:
    """A single flagged issue in the manuscript."""
    checker: str
    severity: Severity
    line: int
    message: str
    match: str = ""
    context: str = ""
    suggestion: str = ""


@dataclass(frozen=True)
class CheckerResult:
    """Result from a single checker run."""
    checker_name: str
    issues: tuple[Issue, ...] = ()
    metrics: dict[str, float | int | str] = field(default_factory=dict)
    summary: str = ""


class Checker(Protocol):
    """Protocol that all checkers must satisfy."""

    name: str
    description: str

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        """Run the check on the given text. Return structured result."""
        ...
