from __future__ import annotations

import json
from pathlib import Path

import pytest

from destination_guard import DestinationGuard, ResolutionError


def test_file_value_resolver_reads_relative_fixture(tmp_path: Path) -> None:
    (tmp_path / "identity.json").write_text(
        json.dumps({"account": {"id": "mailbox_fixture", "name": "Fixture Mailbox"}}),
        encoding="utf-8",
    )
    registry = {
        "pins": {
            "email": {
                "expected_id": "mailbox_fixture",
                "expected_name": "Fixture Mailbox",
                "resolver": {
                    "type": "file_value",
                    "path": "identity.json",
                    "id_path": "account.id",
                    "name_path": "account.name",
                },
                "response_id_path": "mailbox_id",
            }
        }
    }
    registry_path = tmp_path / "pins.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    identity = DestinationGuard.from_file(str(registry_path), output=None).preflight("email")
    assert identity.name == "Fixture Mailbox"


def test_unreadable_file_identity_fails_closed(tmp_path: Path) -> None:
    registry = {
        "pins": {
            "email": {
                "expected_id": "mailbox_fixture",
                "resolver": {
                    "type": "file_value",
                    "path": "missing.json",
                    "id_path": "account.id",
                },
                "response_id_path": "mailbox_id",
            }
        }
    }
    registry_path = tmp_path / "pins.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(ResolutionError, match="cannot resolve identity"):
        DestinationGuard.from_file(str(registry_path), output=None).preflight("email")
