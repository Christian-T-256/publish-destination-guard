"""Small immutable values shared across the package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Identity:
    """A destination identity resolved from a credential or send response."""

    destination_id: str
    name: str = ""


@dataclass(frozen=True)
class Pin:
    """A registry entry describing an expected outbound destination."""

    key: str
    expected_id: str
    expected_name: str
    resolver: Mapping[str, Any]
    response_id_path: str
    response_name_path: str = ""


@dataclass(frozen=True)
class AuditResult:
    """One read-only destination audit result."""

    pin: str
    status: str
    expected_id: str
    resolved_id: str = ""
    resolved_name: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OK"
