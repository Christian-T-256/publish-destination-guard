"""Load and validate a destination pin registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import MissingPinError, RegistryError
from .models import Pin


class PinRegistry:
    """A validated set of named destination pins."""

    def __init__(self, pins: dict[str, Pin], base_dir: Path) -> None:
        self._pins = pins
        self.base_dir = base_dir

    @classmethod
    def from_file(cls, path: str | Path) -> "PinRegistry":
        registry_path = Path(path).expanduser().resolve()
        try:
            raw = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(f"cannot read registry {registry_path}: {exc}") from exc

        raw_pins = raw.get("pins") if isinstance(raw, dict) else None
        if not isinstance(raw_pins, dict) or not raw_pins:
            raise RegistryError("registry must contain a non-empty 'pins' object")

        pins: dict[str, Pin] = {}
        for key, value in raw_pins.items():
            pins[key] = cls._parse_pin(key, value)
        return cls(pins, registry_path.parent)

    @staticmethod
    def _parse_pin(key: Any, value: Any) -> Pin:
        if not isinstance(key, str) or not key.strip():
            raise RegistryError("every pin needs a non-empty string key")
        if not isinstance(value, dict):
            raise RegistryError(f"pin '{key}' must be an object")

        expected_id = value.get("expected_id")
        if not isinstance(expected_id, str) or not expected_id.strip():
            raise RegistryError(f"pin '{key}' needs a non-empty expected_id")
        resolver = value.get("resolver")
        if not isinstance(resolver, dict) or not resolver.get("type"):
            raise RegistryError(f"pin '{key}' needs resolver.type")
        response_id_path = value.get("response_id_path")
        if not isinstance(response_id_path, str) or not response_id_path.strip():
            raise RegistryError(f"pin '{key}' needs a response_id_path")

        return Pin(
            key=key,
            expected_id=expected_id,
            expected_name=str(value.get("expected_name", "")),
            resolver=resolver,
            response_id_path=response_id_path,
            response_name_path=str(value.get("response_name_path", "")),
        )

    def get(self, key: str) -> Pin:
        try:
            return self._pins[key]
        except KeyError as exc:
            raise MissingPinError(f"no destination pin named '{key}'") from exc

    def all(self) -> tuple[Pin, ...]:
        return tuple(self._pins.values())
