class BlackboardError(Exception):
    """Base exception for Blackboard errors."""
    pass


class InvalidMessageError(BlackboardError):
    """Raised when a PXP message fails validation."""
    pass


class BlackboardNotInitializedError(BlackboardError):
    """Raised when operations require an initialized Blackboard."""
    pass


class InvalidStatusTransitionError(BlackboardError):
    """Raised when an invalid status transition is attempted."""
    pass


class SnapshotError(BlackboardError):
    """Raised when snapshot operations fail."""
    pass