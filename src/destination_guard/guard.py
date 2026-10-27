"""Fail-closed preflight and post-send verification."""

from __future__ import annotations

import functools
from contextlib import contextmanager
from typing import Any, Callable, Generator, ParamSpec, TypeVar

from .errors import DestinationMismatchError, PostSendVerificationError
from .models import AuditResult, Identity, Pin
from .registry import PinRegistry
from .resolvers import ResolverRegistry, dotted_value

P = ParamSpec("P")
R = TypeVar("R")


class GuardSession:
    """A preflighted context that must receive a verifiable send response."""

    def __init__(self, guard: "DestinationGuard", pin: Pin, identity: Identity) -> None:
        self._guard = guard
        self.pin = pin
        self.identity = identity
        self._confirmed = False

    def confirm(self, response: Any) -> Identity:
        identity = self._guard.verify_response(self.pin, response)
        self._confirmed = True
        self._guard._emit_success("SEND", self.pin, identity)
        return identity

    @property
    def confirmed(self) -> bool:
        return self._confirmed


class DestinationGuard:
    """Proves an outbound operation's destination before and after sending."""

    def __init__(
        self,
        registry: PinRegistry,
        resolvers: ResolverRegistry | None = None,
        output: Callable[[str], None] | None = print,
    ) -> None:
        self.registry = registry
        self.resolvers = resolvers or ResolverRegistry()
        self.output = output

    @classmethod
    def from_file(
        cls,
        path: str,
        resolvers: ResolverRegistry | None = None,
        output: Callable[[str], None] | None = print,
    ) -> "DestinationGuard":
        return cls(PinRegistry.from_file(path), resolvers=resolvers, output=output)

    def preflight(self, pin_name: str) -> Identity:
        pin = self.registry.get(pin_name)
        identity = self.resolvers.resolve(pin, self.registry.base_dir)
        self._require_match(pin, identity, "credential")
        self._emit_success("PREFLIGHT", pin, identity)
        return identity

    def verify_response(self, pin: Pin, response: Any) -> Identity:
        try:
            destination_id = dotted_value(response, pin.response_id_path)
            name = dotted_value(response, pin.response_name_path) if pin.response_name_path else ""
        except Exception as exc:
            raise PostSendVerificationError(
                f"send completed for pin '{pin.key}', but the response did not prove field "
                f"'{pin.response_id_path}'"
            ) from exc
        identity = Identity(str(destination_id), str(name or ""))
        self._require_match(pin, identity, "send response")
        return identity

    def execute(self, pin_name: str, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        self.preflight(pin_name)
        pin = self.registry.get(pin_name)
        response = operation(*args, **kwargs)
        identity = self.verify_response(pin, response)
        self._emit_success("SEND", pin, identity)
        return response

    def guarded(self, pin_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorate a send function with preflight and response verification."""
        def decorate(operation: Callable[P, R]) -> Callable[P, R]:
            @functools.wraps(operation)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                return self.execute(pin_name, operation, *args, **kwargs)

            return wrapped

        return decorate

    @contextmanager
    def context(self, pin_name: str) -> Generator[GuardSession, None, None]:
        """Preflight a manual send and require ``session.confirm(response)``."""
        identity = self.preflight(pin_name)
        session = GuardSession(self, self.registry.get(pin_name), identity)
        yield session
        if not session.confirmed:
            raise PostSendVerificationError(
                f"guarded block for pin '{pin_name}' exited without confirming the send response"
            )

    def audit(self) -> list[AuditResult]:
        """Resolve every pin without sending anything."""
        results: list[AuditResult] = []
        for pin in self.registry.all():
            try:
                identity = self.resolvers.resolve(pin, self.registry.base_dir)
                self._require_match(pin, identity, "credential")
                results.append(
                    AuditResult(pin.key, "OK", pin.expected_id, identity.destination_id, identity.name)
                )
            except DestinationMismatchError as exc:
                results.append(AuditResult(pin.key, "MISMATCH", pin.expected_id, detail=str(exc)))
            except Exception as exc:
                results.append(AuditResult(pin.key, "UNRESOLVED", pin.expected_id, detail=str(exc)))
        return results

    @staticmethod
    def _require_match(pin: Pin, identity: Identity, source: str) -> None:
        if not identity.destination_id:
            raise DestinationMismatchError(
                f"{source} returned an empty destination for pin '{pin.key}'"
            )
        if identity.destination_id != pin.expected_id:
            raise DestinationMismatchError(
                f"{source} mismatch for pin '{pin.key}': expected '{pin.expected_id}', "
                f"resolved '{identity.destination_id}'"
            )

    def _emit_success(self, phase: str, pin: Pin, identity: Identity) -> None:
        if self.output:
            name = identity.name or pin.expected_name or "unnamed"
            self.output(
                f'{phase} OK pin={pin.key} destination="{name}" id={identity.destination_id}'
            )
