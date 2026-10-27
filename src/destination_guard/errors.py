"""Exception hierarchy for destination guard failures."""


class DestinationGuardError(RuntimeError):
    """Base class for errors that must stop an outbound operation."""


class RegistryError(DestinationGuardError):
    """The registry is absent, malformed, or contains an invalid pin."""


class MissingPinError(DestinationGuardError):
    """No destination pin exists for the requested integration."""


class ResolutionError(DestinationGuardError):
    """The credential's current destination could not be resolved."""


class DestinationMismatchError(DestinationGuardError):
    """The resolved or returned destination differs from the pin."""


class PostSendVerificationError(DestinationGuardError):
    """A send completed but its response could not prove the destination."""
