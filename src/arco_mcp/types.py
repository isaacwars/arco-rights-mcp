"""Dataclasses for ARCO error types. Gives the LLM structured reasoning tokens."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """Base finding — all errors and warnings share this shape."""
    code: str
    message: str
    severity: str  # "critical" | "high" | "medium" | "low"


@dataclass(frozen=True, slots=True)
class Blocker(ValidationFinding):
    """A critical issue that prevents drafting. severity is always 'critical'."""
    severity: str = "critical"


@dataclass(frozen=True, slots=True)
class Warning(ValidationFinding):
    """A non-blocking issue. severity is 'high', 'medium', or 'low'."""
    pass


@dataclass(frozen=True, slots=True)
class MissingField:
    """A required field path that is empty, placeholder, or absent."""
    path: str
    code: str = "missing_field"


@dataclass(frozen=True, slots=True)
class PlaceholderFound:
    """A field contains placeholder text instead of real data."""
    path: str
    code: str = "placeholder_found"


@dataclass(frozen=True, slots=True)
class SensitiveNotMarked:
    """Data that requires sensitive=true but is marked false."""
    index: int
    categoria: str
    code: str = "data_requires_sensitive_treatment"


@dataclass(frozen=True, slots=True)
class CaseSummary:
    """Compact summary for the LLM to decide next action without parsing full output."""
    ready: bool
    total_blockers: int
    total_warnings: int
    total_missing: int
    blocker_codes: list[str] = field(default_factory=list)
    next_step: str = ""

    @classmethod
    def from_validation(cls, validation: dict) -> "CaseSummary":
        blockers = validation.get("blockers", [])
        return cls(
            ready=validation.get("ready_to_draft", False),
            total_blockers=len(blockers),
            total_warnings=len(validation.get("warnings", [])),
            total_missing=len(validation.get("missing", [])),
            blocker_codes=[b.get("code", "") for b in blockers if isinstance(b, dict)],
            next_step=(
                "ready" if validation.get("ready_to_draft")
                else "resolve_blockers"
            ),
        )


def blocker(code: str, message: str) -> dict[str, str]:
    """Shorthand to create a blocker dict (backward compat with existing engine)."""
    return {"code": code, "message": message, "severity": "critical"}


def warning(code: str, severity: str, message: str) -> dict[str, str]:
    """Shorthand to create a warning dict (backward compat with existing engine)."""
    return {"code": code, "severity": severity, "message": message}
