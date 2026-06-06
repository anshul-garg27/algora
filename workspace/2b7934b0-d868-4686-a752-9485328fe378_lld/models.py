"""Core value objects, enums, and domain errors for the Splitwise design."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class SplitType(Enum):
    """The supported ways to divide an expense among participants."""
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    PERCENT = "PERCENT"


# --- Domain errors: specific types so callers can react precisely ---
class SplitwiseError(Exception):
    """Base class for all domain errors."""


class UserNotFoundError(SplitwiseError):
    """A referenced user id is not registered."""


class InvalidAmountError(SplitwiseError):
    """Amount is non-positive or otherwise invalid."""


class InvalidSplitError(SplitwiseError):
    """Split inputs are inconsistent (don't sum to total, wrong count, etc.)."""


class DuplicateExpenseError(SplitwiseError):
    """An expense id was reused."""


@dataclass(frozen=True)
class User:
    """Immutable identity of a participant."""
    id: str
    name: str
    email: str


@dataclass(frozen=True)
class Split:
    """One participant's share of one expense, in integer cents (immutable)."""
    user_id: str
    amount_cents: int


@dataclass(frozen=True)
class Expense:
    """Immutable record of one shared cost. Invariant: splits sum to amount_cents."""
    id: str
    description: str
    amount_cents: int
    paid_by: str
    splits: Tuple[Split, ...]
    created_at: float


def to_cents(amount: float) -> int:
    """Convert a dollar amount to integer cents, rounding half-up at the penny."""
    return int(round(amount * 100))
