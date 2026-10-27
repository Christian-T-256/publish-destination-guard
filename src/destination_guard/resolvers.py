"""Built-in credential identity resolvers and plugin registration."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Protocol

from .errors import RegistryError, ResolutionError
from .models import Identity, Pin

_ENV_REFERENCE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")


def dotted_value(data: Any, path: str) -> Any:
    """Read a dotted path such as ``account.id`` from a JSON-like object."""
    current = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            raise ResolutionError(f"identity response has no field '{path}'")
    return current


class Resolver(Protocol):
    def resolve(self, pin: Pin, base_dir: Path) -> Identity:
        """Resolve the current credential identity or raise ResolutionError."""


class MockResolver:
    """Resolve a fictional in-registry identity for tests and local demos."""

    def resolve(self, pin: Pin, base_dir: Path) -> Identity:
        destination_id = pin.resolver.get("identity_id")
        if not destination_id:
            raise ResolutionError("mock resolver needs identity_id")
        return Identity(str(destination_id), str(pin.resolver.get("identity_name", "")))


class FileValueResolver:
    """Resolve identity from a local JSON file written by credential tooling."""

    def resolve(self, pin: Pin, base_dir: Path) -> Identity:
        configured_path = pin.resolver.get("path")
        field = pin.resolver.get("id_path")
        if not configured_path or not field:
            raise ResolutionError("file_value resolver needs path and id_path")
        path = Path(str(configured_path)).expanduser()
        if not path.is_absolute():
            path = base_dir / path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            destination_id = dotted_value(data, str(field))
            name_path = pin.resolver.get("name_path")
            name = dotted_value(data, str(name_path)) if name_path else ""
        except ResolutionError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ResolutionError(f"cannot resolve identity from {path}: {exc}") from exc
        if not destination_id:
            raise ResolutionError(f"identity field '{field}' is empty")
        return Identity(str(destination_id), str(name or ""))


class HttpIdentityResolver:
    """Resolve identity from a credential-aware HTTP who-am-I endpoint."""

    def resolve(self, pin: Pin, base_dir: Path) -> Identity:
        url = pin.resolver.get("url")
        field = pin.resolver.get("id_path")
        if not url or not field:
            raise ResolutionError("http_identity resolver needs url and id_path")

        headers: dict[str, str] = {}
        for name, raw_value in pin.resolver.get("headers", {}).items():
            match = _ENV_REFERENCE.fullmatch(str(raw_value))
            if match:
                env_name = match.group(1)
                value = os.environ.get(env_name)
                if not value:
                    raise ResolutionError(f"required environment variable {env_name} is not set")
                headers[str(name)] = value
            else:
                headers[str(name)] = str(raw_value)

        request = urllib.request.Request(str(url), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=float(pin.resolver.get("timeout", 10))) as response:
                data = json.loads(response.read().decode("utf-8"))
            destination_id = dotted_value(data, str(field))
            name_path = pin.resolver.get("name_path")
            name = dotted_value(data, str(name_path)) if name_path else ""
        except ResolutionError:
            raise
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            raise ResolutionError(f"HTTP identity lookup failed: {type(exc).__name__}") from exc
        if not destination_id:
            raise ResolutionError(f"identity field '{field}' is empty")
        return Identity(str(destination_id), str(name or ""))


class ResolverRegistry:
    """Maps resolver type names to implementations and accepts custom plugins."""

    def __init__(self) -> None:
        self._resolvers: dict[str, Resolver] = {
            "mock": MockResolver(),
            "file_value": FileValueResolver(),
            "http_identity": HttpIdentityResolver(),
        }

    def register(self, name: str, resolver: Resolver) -> None:
        if not name:
            raise ValueError("resolver name cannot be empty")
        self._resolvers[name] = resolver

    def resolve(self, pin: Pin, base_dir: Path) -> Identity:
        resolver_type = str(pin.resolver.get("type", ""))
        try:
            resolver = self._resolvers[resolver_type]
        except KeyError as exc:
            raise RegistryError(f"pin '{pin.key}' uses unknown resolver '{resolver_type}'") from exc
        return resolver.resolve(pin, base_dir)
