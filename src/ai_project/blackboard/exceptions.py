class BlackboardError(Exception):
    """Base exception for Blackboard errors."""


class InvalidMessageError(BlackboardError):
    """A message failed the PXP grammar. ``violations`` lists every problem."""

    def __init__(self, message: str, violations: list | None = None) -> None:
        super().__init__(message)
        self.violations = list(violations or [])


class VersionConflict(BlackboardError):
    """The board changed between an agent's read and its write."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"Board is at version {actual}, write expected version {expected}")
        self.expected = expected
        self.actual = actual


class BlackboardNotInitializedError(BlackboardError):
    """Raised when an operation needs a task and none has been set."""


class InvalidStatusTransitionError(BlackboardError):
    """Raised for a status change not in STATUS_TRANSITIONS."""


class StoreError(BlackboardError):
    """Raised when a store cannot read or write a session."""
