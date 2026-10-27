"""Public API for publish-destination-guard."""

from .errors import (
    DestinationGuardError,
    DestinationMismatchError,
    MissingPinError,
    PostSendVerificationError,
    RegistryError,
    ResolutionError,
)
from .guard import DestinationGuard, GuardSession
from .models import AuditResult, Identity, Pin
from .registry import PinRegistry
from .resolvers import Resolver, ResolverRegistry

__all__ = [
    "AuditResult",
    "DestinationGuard",
    "DestinationGuardError",
    "DestinationMismatchError",
    "GuardSession",
    "Identity",
    "MissingPinError",
    "Pin",
    "PinRegistry",
    "PostSendVerificationError",
    "RegistryError",
    "ResolutionError",
    "Resolver",
    "ResolverRegistry",
]
