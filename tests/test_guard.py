from __future__ import annotations

import json
from pathlib import Path

import pytest

from destination_guard import (
    DestinationGuard,
    DestinationMismatchError,
    MissingPinError,
    PostSendVerificationError,
)


def write_registry(tmp_path: Path, *, expected: str = "channel_expected", actual: str = "channel_expected") -> Path:
    registry = {
        "pins": {
            "video": {
                "expected_id": expected,
                "expected_name": "Northwind Dental Video",
                "resolver": {
                    "type": "mock",
                    "identity_id": actual,
                    "identity_name": "Northwind Dental Video",
                },
                "response_id_path": "destination.id",
                "response_name_path": "destination.name",
            }
        }
    }
    path = tmp_path / "pins.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def test_mismatch_refuses_before_send(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(
        str(write_registry(tmp_path, actual="wrong_channel")), output=None
    )
    called = False

    def send() -> dict[str, object]:
        nonlocal called
        called = True
        return {"destination": {"id": "channel_expected"}}

    with pytest.raises(DestinationMismatchError, match="credential mismatch"):
        guard.execute("video", send)
    assert called is False


def test_missing_pin_refuses_before_send(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=None)
    called = False

    def send() -> dict[str, object]:
        nonlocal called
        called = True
        return {"destination": {"id": "channel_expected"}}

    with pytest.raises(MissingPinError, match="no destination pin"):
        guard.execute("unknown", send)
    assert called is False


def test_post_send_drift_is_reported(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=None)

    def send() -> dict[str, object]:
        return {"destination": {"id": "drifted_channel", "name": "Unexpected"}}

    with pytest.raises(DestinationMismatchError, match="send response mismatch"):
        guard.execute("video", send)


def test_missing_destination_in_response_fails_closed(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=None)
    with pytest.raises(PostSendVerificationError, match="did not prove"):
        guard.execute("video", lambda: {"status": "accepted"})


def test_decorator_guards_send_and_echoes_destination(tmp_path: Path) -> None:
    lines: list[str] = []
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=lines.append)

    @guard.guarded("video")
    def send(title: str) -> dict[str, object]:
        return {
            "title": title,
            "destination": {"id": "channel_expected", "name": "Northwind Dental Video"},
        }

    assert send("Fictional update")["title"] == "Fictional update"
    assert lines == [
        'PREFLIGHT OK pin=video destination="Northwind Dental Video" id=channel_expected',
        'SEND OK pin=video destination="Northwind Dental Video" id=channel_expected',
    ]


def test_context_manager_requires_confirmation(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=None)
    with pytest.raises(PostSendVerificationError, match="without confirming"):
        with guard.context("video"):
            pass


def test_context_manager_confirms_response(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(str(write_registry(tmp_path)), output=None)
    with guard.context("video") as session:
        identity = session.confirm(
            {"destination": {"id": "channel_expected", "name": "Northwind Dental Video"}}
        )
    assert identity.destination_id == "channel_expected"


def test_audit_reports_mismatch_instead_of_raising(tmp_path: Path) -> None:
    guard = DestinationGuard.from_file(
        str(write_registry(tmp_path, actual="wrong_channel")), output=None
    )
    result = guard.audit()[0]
    assert result.status == "MISMATCH"
    assert result.ok is False
